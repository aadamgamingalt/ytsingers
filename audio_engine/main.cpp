#include <iostream>
#include <string>
#include <vector>
#include <complex>
#include <cmath>
#include <algorithm>
#include <sndfile.h>

static const double PI = 3.14159265358979323846;

// ── helpers ──────────────────────────────────────────────────────────────────

static void hann_window(std::vector<float>& w)
{
    int n = (int)w.size();
    for (int i = 0; i < n; i++)
        w[i] = 0.5f * (1.0f - std::cos(2.0f * PI * i / (n - 1)));
}

// In-place radix-2 Cooley-Tukey FFT (size must be power of 2)
static void fft(std::vector<std::complex<double>>& x, bool inverse)
{
    int n = (int)x.size();
    for (int i = 1, j = 0; i < n; i++) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(x[i], x[j]);
    }
    for (int len = 2; len <= n; len <<= 1) {
        double ang = 2.0 * PI / len * (inverse ? -1 : 1);
        std::complex<double> wlen(std::cos(ang), std::sin(ang));
        for (int i = 0; i < n; i += len) {
            std::complex<double> w(1.0, 0.0);
            for (int j = 0; j < len / 2; j++) {
                auto u = x[i + j], v = x[i + j + len/2] * w;
                x[i + j]          = u + v;
                x[i + j + len/2]  = u - v;
                w *= wlen;
            }
        }
    }
    if (inverse) for (auto& c : x) c /= n;
}

// ── pitch detection via autocorrelation (YIN-inspired) ──────────────────────

static double detect_pitch_hz(const std::vector<float>& audio, int sr)
{
    int n    = std::min((int)audio.size(), sr / 4); // max 250 ms window
    int minL = sr / 1000;   // 1000 Hz max
    int maxL = sr / 60;     //   60 Hz min

    double bestCorr = -1e9;
    int    bestLag  = maxL;

    for (int lag = minL; lag < maxL && lag < n; lag++) {
        double corr = 0, norm = 0;
        for (int i = 0; i < n - lag; i++) {
            corr += (double)audio[i] * audio[i + lag];
            norm += (double)audio[i] * audio[i];
        }
        if (norm > 0) corr /= norm;
        if (corr > bestCorr) { bestCorr = corr; bestLag = lag; }
    }
    return bestLag > 0 ? (double)sr / bestLag : 220.0;
}

// ── phase vocoder pitch shift (no tempo change) ──────────────────────────────

static std::vector<float> pitch_shift(
    const std::vector<float>& input,
    int sr,
    double pitch_ratio,   // e.g. 1.5 = up a fifth, 0.5 = down an octave
    int fft_size  = 2048,
    int hop_size  = 512)
{
    int n = (int)input.size();

    // Build Hann window
    std::vector<float> win(fft_size);
    hann_window(win);

    // Phase accumulators
    std::vector<double> phase_in(fft_size / 2 + 1, 0.0);
    std::vector<double> phase_out(fft_size / 2 + 1, 0.0);

    // Output buffer
    std::vector<float> output(n + fft_size, 0.0f);
    std::vector<float> overlap(n + fft_size, 0.0f);

    int syn_hop = (int)std::round(hop_size * pitch_ratio);
    if (syn_hop < 1) syn_hop = 1;

    int out_pos = 0;

    for (int pos = 0; pos + fft_size <= n; pos += hop_size) {
        // Window the frame
        std::vector<std::complex<double>> frame(fft_size);
        for (int i = 0; i < fft_size; i++)
            frame[i] = (double)input[pos + i] * win[i];

        // Forward FFT
        fft(frame, false);

        // Phase vocoder: compute true frequencies
        std::vector<double> magnitude(fft_size / 2 + 1);
        std::vector<double> true_freq(fft_size / 2 + 1);

        for (int k = 0; k <= fft_size / 2; k++) {
            double mag   = std::abs(frame[k]);
            double phase = std::arg(frame[k]);

            double expected = 2.0 * PI * k * hop_size / fft_size;
            double delta    = phase - phase_in[k] - expected;

            // Wrap to [-pi, pi]
            delta -= 2.0 * PI * std::round(delta / (2.0 * PI));

            true_freq[k]  = (expected + delta) * sr / (2.0 * PI * hop_size);
            magnitude[k]  = mag;
            phase_in[k]   = phase;
        }

        // Accumulate output phases
        std::vector<std::complex<double>> out_frame(fft_size, {0.0, 0.0});
        for (int k = 0; k <= fft_size / 2; k++) {
            phase_out[k] += 2.0 * PI * true_freq[k] * syn_hop / sr;
            out_frame[k]  = std::polar(magnitude[k], phase_out[k]);
        }

        // Mirror for real IFFT
        for (int k = 1; k < fft_size / 2; k++)
            out_frame[fft_size - k] = std::conj(out_frame[k]);

        // Inverse FFT
        fft(out_frame, true);

        // Overlap-add with Hann window
        for (int i = 0; i < fft_size && out_pos + i < (int)output.size(); i++) {
            output[out_pos + i] += (float)(out_frame[i].real() * win[i]);
            overlap[out_pos + i] += win[i] * win[i];
        }
        out_pos += syn_hop;
    }

    // Normalise by overlap
    for (int i = 0; i < (int)output.size(); i++)
        if (overlap[i] > 1e-8f) output[i] /= overlap[i];

    // Time-stretch back to original length (linear resample)
    std::vector<float> result(n);
    double scale = (double)output.size() / n;
    for (int i = 0; i < n; i++) {
        double src = i * scale;
        int    lo  = (int)src;
        double frac = src - lo;
        int    hi  = std::min(lo + 1, (int)output.size() - 1);
        result[i]  = (float)((1.0 - frac) * output[lo] + frac * output[hi]);
    }
    return result;
}

// ── I/O helpers ──────────────────────────────────────────────────────────────

static std::vector<float> read_audio(const std::string& path, SF_INFO& info)
{
    SNDFILE* f = sf_open(path.c_str(), SFM_READ, &info);
    if (!f) { std::cerr << "Cannot open " << path << ": " << sf_strerror(nullptr) << "\n"; return {}; }
    std::vector<float> buf(info.frames * info.channels);
    sf_readf_float(f, buf.data(), info.frames);
    sf_close(f);
    // Mix to mono
    if (info.channels > 1) {
        std::vector<float> mono(info.frames);
        for (int i = 0; i < info.frames; i++) {
            float s = 0;
            for (int c = 0; c < info.channels; c++) s += buf[i * info.channels + c];
            mono[i] = s / info.channels;
        }
        info.channels = 1;
        return mono;
    }
    return buf;
}

static bool write_audio(const std::string& path, const std::vector<float>& audio, SF_INFO info)
{
    info.channels = 1;
    SNDFILE* f = sf_open(path.c_str(), SFM_WRITE, &info);
    if (!f) { std::cerr << "Cannot write " << path << ": " << sf_strerror(nullptr) << "\n"; return false; }
    sf_writef_float(f, audio.data(), (sf_count_t)audio.size());
    sf_close(f);
    return true;
}

// ── commands ─────────────────────────────────────────────────────────────────

// pitchshift <input.wav> <target_hz> <output.wav>
static int cmd_pitchshift(int argc, char* argv[])
{
    if (argc < 5) { std::cerr << "Usage: pitchshift <in.wav> <target_hz> <out.wav>\n"; return 1; }
    std::string in_path  = argv[2];
    double      target   = std::stod(argv[3]);
    std::string out_path = argv[4];

    SF_INFO info = {};
    auto audio = read_audio(in_path, info);
    if (audio.empty()) return 1;

    double source = detect_pitch_hz(audio, info.samplerate);
    if (source < 50 || source > 2000) source = 220.0;

    double ratio = target / source;
    std::cout << "Source: " << source << " Hz -> Target: " << target
              << " Hz (ratio: " << ratio << ")\n";

    auto shifted = pitch_shift(audio, info.samplerate, ratio);
    return write_audio(out_path, shifted, info) ? 0 : 1;
}

// detect <input.wav>  -- prints detected pitch in Hz
static int cmd_detect(int argc, char* argv[])
{
    if (argc < 3) { std::cerr << "Usage: detect <in.wav>\n"; return 1; }
    SF_INFO info = {};
    auto audio = read_audio(argv[2], info);
    if (audio.empty()) return 1;
    double hz = detect_pitch_hz(audio, info.samplerate);
    std::cout << hz << "\n";
    return 0;
}

int main(int argc, char* argv[])
{
    if (argc < 2) {
        std::cerr << "ytsingers audio engine\n"
                  << "Commands:\n"
                  << "  pitchshift <in.wav> <target_hz> <out.wav>\n"
                  << "  detect     <in.wav>\n";
        return 1;
    }
    std::string cmd = argv[1];
    if (cmd == "pitchshift") return cmd_pitchshift(argc, argv);
    if (cmd == "detect")     return cmd_detect(argc, argv);
    std::cerr << "Unknown command: " << cmd << "\n";
    return 1;
}

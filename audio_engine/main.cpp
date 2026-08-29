#include <iostream>
#include <string>
#include <cmath>
#include <vector>
#include <sndfile.h>
#include <rubberband/RubberBandStretcher.h>

using namespace RubberBand;

// Detect pitch of audio using autocorrelation (YIN-like)
double detect_pitch(const std::vector<float>& audio, int sr) {
    int n = std::min((int)audio.size(), 4096);
    double best_freq = 220.0;
    double best_corr = -1.0;

    for (int lag = sr / 800; lag < sr / 50; lag++) {
        double corr = 0;
        for (int i = 0; i < n - lag; i++) {
            corr += audio[i] * audio[i + lag];
        }
        corr /= (n - lag);
        if (corr > best_corr) {
            best_corr = corr;
            best_freq = (double)sr / lag;
        }
    }
    return best_freq;
}

int pitchshift(const std::string& input, double target_hz, const std::string& output) {
    // Open input
    SF_INFO in_info = {};
    SNDFILE* in_file = sf_open(input.c_str(), SFM_READ, &in_info);
    if (!in_file) {
        std::cerr << "Cannot open input: " << sf_strerror(nullptr) << std::endl;
        return 1;
    }

    int sr = in_info.samplerate;
    int channels = in_info.channels;
    int frames = in_info.frames;

    // Read audio
    std::vector<float> audio(frames * channels);
    sf_readf_float(in_file, audio.data(), frames);
    sf_close(in_file);

    // Convert to mono for pitch detection
    std::vector<float> mono(frames);
    for (int i = 0; i < frames; i++) {
        float sum = 0;
        for (int c = 0; c < channels; c++) sum += audio[i * channels + c];
        mono[i] = sum / channels;
    }

    // Detect source pitch
    double source_hz = detect_pitch(mono, sr);
    if (source_hz < 50 || source_hz > 2000) source_hz = 220.0;

    // Calculate semitone shift
    double semitones = 12.0 * std::log2(target_hz / source_hz);

    std::cout << "Source: " << source_hz << " Hz -> Target: " << target_hz
              << " Hz (shift: " << semitones << " semitones)" << std::endl;

    // Setup Rubber Band
    RubberBandStretcher::Options opts =
        RubberBandStretcher::OptionProcessOffline |
        RubberBandStretcher::OptionPitchHighQuality |
        RubberBandStretcher::OptionFormantPreserved;  // No chipmunk!

    RubberBandStretcher stretcher(sr, channels, opts);
    stretcher.setTimeRatio(1.0);  // No time stretch, pitch only
    stretcher.setPitchScale(std::pow(2.0, semitones / 12.0));

    // Process in chunks
    int block = 1024;
    stretcher.setExpectedInputDuration(frames);

    // Study pass (for offline mode)
    for (int pos = 0; pos < frames; pos += block) {
        int n = std::min(block, frames - pos);
        bool last = (pos + n >= frames);

        std::vector<float*> ptrs(channels);
        std::vector<std::vector<float>> bufs(channels, std::vector<float>(n));
        for (int c = 0; c < channels; c++) {
            for (int i = 0; i < n; i++) bufs[c][i] = audio[(pos + i) * channels + c];
            ptrs[c] = bufs[c].data();
        }
        stretcher.study(ptrs.data(), n, last);
    }

    // Process pass
    std::vector<float> out_audio;
    for (int pos = 0; pos < frames; pos += block) {
        int n = std::min(block, frames - pos);
        bool last = (pos + n >= frames);

        std::vector<float*> ptrs(channels);
        std::vector<std::vector<float>> bufs(channels, std::vector<float>(n));
        for (int c = 0; c < channels; c++) {
            for (int i = 0; i < n; i++) bufs[c][i] = audio[(pos + i) * channels + c];
            ptrs[c] = bufs[c].data();
        }
        stretcher.process(ptrs.data(), n, last);

        while (stretcher.available() > 0) {
            int avail = stretcher.available();
            std::vector<std::vector<float>> out_bufs(channels, std::vector<float>(avail));
            std::vector<float*> out_ptrs(channels);
            for (int c = 0; c < channels; c++) out_ptrs[c] = out_bufs[c].data();
            stretcher.retrieve(out_ptrs.data(), avail);
            for (int i = 0; i < avail; i++) {
                for (int c = 0; c < channels; c++) out_audio.push_back(out_bufs[c][i]);
            }
        }
    }

    // Write output
    SF_INFO out_info = in_info;
    out_info.frames = out_audio.size() / channels;
    SNDFILE* out_file = sf_open(output.c_str(), SFM_WRITE, &out_info);
    if (!out_file) {
        std::cerr << "Cannot open output: " << sf_strerror(nullptr) << std::endl;
        return 1;
    }
    sf_writef_float(out_file, out_audio.data(), out_info.frames);
    sf_close(out_file);

    return 0;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: audio_engine <command> [args...]" << std::endl;
        std::cerr << "Commands:" << std::endl;
        std::cerr << "  pitchshift <input.wav> <target_hz> <output.wav>" << std::endl;
        return 1;
    }

    std::string cmd = argv[1];
    if (cmd == "pitchshift" && argc == 5) {
        return pitchshift(argv[2], std::stod(argv[3]), argv[4]);
    }

    std::cerr << "Unknown command: " << cmd << std::endl;
    return 1;
}


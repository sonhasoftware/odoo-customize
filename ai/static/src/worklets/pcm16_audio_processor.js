/** @odoo-module */
// This class has several responsibility:
// - Merge the channels of an stereo audio source that to a mono output,
// - Down-sample the original input to a certain sample rate (i.e. 24kHz),
// - Finally, buffer the audio to send bigger chunks at a time.
class PCM16AudioProcessor extends AudioWorkletProcessor {
    constructor(options) {
        super(options);

        this.maxBufferSize = 6000;
        this.buffer = new Int16Array(this.maxBufferSize);
        this.nextInsertPointer = 0; // Next position to insert data into the buffer
    }

    /**
     * Main method of the worklet, used to process audio and send it to the result to the main thread
     *
     * @param {Array<Array<Float32Array>>} inputs the list of inputs. Each of them containing a list of channels.
     * @returns {boolean} true to force the worklet to stay active, false otherwise.
     */
    process(inputs) {
        const input = inputs[0];

        if (input.length > 0) {
            const inputChannel = this.combine(input);

            // Here we down-sample the input channel to 24kHz
            // This is used by the real-time transcription feature to be compliant
            // with OpenAI's APIs
            // sampleRate is injected from the AudioWorkletGlobalScope from audioContext.sampleRate
            // eslint-disable-next-line no-undef
            const downsampledChannel = this.downsample(inputChannel, sampleRate, 24000);
            for (let i = 0; i < downsampledChannel.length; i++) {
                const sample = Math.max(-1, Math.min(1, downsampledChannel[i]));

                // If the next insert position is bellow the max buffer size
                // then we insert a new element
                // Otherwise
                // We commit the buffer and reset the insert pointer
                if (this.nextInsertPointer < this.maxBufferSize) {
                    // Converting Float32 into Int16
                    this.buffer[this.nextInsertPointer] =
                        sample < 0 ? sample * 0x8000 : sample * 0x7fff;
                    this.nextInsertPointer++;
                } else {
                    this.port.postMessage(this.buffer.buffer);
                    this.buffer = new Int16Array(this.maxBufferSize);
                    this.nextInsertPointer = 0;
                }
            }
        }

        return true;
    }

    /**
     * Downsamples the buffer from the inputRate to the outputRate.
     * The downsampling will take every inputRate/outputRate samples from the input buffer and put them in the ouput.
     * @param {Float32Array} buffer the input audio buffer
     * @param {Number} inputRate the source rate of the buffer
     * @param {Number} outputRate the sampling rate of the output
     * @returns {Float32Array} a downsampled version of the input buffer
     */
    downsample(buffer, inputRate, outputRate) {
        if (inputRate === outputRate) {
            return buffer;
        }

        const rateRatio = inputRate / outputRate;
        const downsampledLength = Math.round(buffer.length / rateRatio);
        const outputBuffer = new Float32Array(downsampledLength);
        for (let i = 0; i < outputBuffer.length; i++) {
            outputBuffer[i] = buffer[Math.floor(i * rateRatio)];
        }

        return outputBuffer;
    }

    /**
     * Combines multi-channels input into a mono channel output.
     * This method will produce a channel where each element is the average
     * of the corresponding elements in the source channels.
     * @param {Array<Float32Array>} channels the channels to combine
     * @returns {Float32Array} the combined channel
     */
    combine(channels) {
        const monoChannel = new Float32Array(channels[0].length);
        for (let i = 0; i < monoChannel.length; i++) {
            for (let j = 0; j < channels.length; j++) {
                monoChannel[i] += channels[j][i];
            }
            monoChannel[i] = monoChannel[i] / channels.length;
        }
        return monoChannel;
    }
}

registerProcessor("pcm16-processor", PCM16AudioProcessor);

import math
import numpy as np


class WindowConfiguration:
    def __init__(self,
                 left_duration=0.1,
                 left_apply_window_start=True,
                 left_apply_window_end=True,
                 left_window_function='Hanning',
                 right_duration=0.1,
                 right_apply_window_start=True,
                 right_apply_window_end=True,
                 right_window_function='Hanning'):
        """

        :param left_duration: (Optional) Duration of the window in seconds, for the left channel. If zero, no window
            will be created for this channel. Default: 0.1s
        :param left_apply_window_start: (Optional) True if the window should be applied to the **start** of the sound
            for the left channel, False otherwise. Default: True
        :param left_apply_window_end: (Optional) True if the window should be applied to the **end** of the sound for
            the left channel, False otherwise. Default: True
        :param left_window_function: (Optional) Window function that should be used for the left channel. Possible values
            accepted: 'Hanning', 'Hamming', 'Blackman', 'Bartlett'. Default: 'Hanning"
        :param right_duration: (Optional) Duration of the window in seconds, for the right channel. If zero, no window
            will be created for this channel. Default: 0.1s
        :param right_apply_window_start: (Optional) True if the
            window should be applied to the **start** of the sound, for the right channel, False otherwise. Default: True
        :param right_apply_window_end: (Optional) True if the window
            should be applied to the **end** of the sound for the right channel, False otherwise. Default: True
        :param right_window_function: (Optional) Window function that should be used for the left channel.
            Possible values accepted: 'Hanning', 'Hamming', 'Blackman', 'Bartlett'. Default: 'Hanning"
        """
        self.left_duration = left_duration
        self.right_duration = right_duration
        self.left_apply_window_start = left_apply_window_start
        self.right_apply_window_start = right_apply_window_start
        self.left_apply_window_end = left_apply_window_end
        self.right_apply_window_end = right_apply_window_end
        self.left_window_function = left_window_function
        self.right_window_function = right_window_function


def generate_sound(filename=None, fs=96000, duration=1, frequency_left=1000, frequency_right=1000, window_configuration:WindowConfiguration=None):
    """
    Helper method to dynamically generated a sound that can be used in with the Sound Card module.

    :param filename: (Optional)
    :param fs: (Optional) number of samples per second (standard)
    :param duration: (Optional) sound duration in seconds
    :param frequency_left: (Optional) number of cycles per second (Hz) (frequency of the sine wave for the left channel)
    :param frequency_right: (Optional) number of cycles per second (Hz) (frequency of the sine wave for the right channel)
    :param window_configuration: (Optional) WindowConfiguration object to apply to the generated sound.

    :return: Returns the **flatten** generated sound as a numpy array (as np.int8)

    """

    amplitude24bits = math.pow(2, 31) - 1

    samples = np.arange(0, duration, 1 / fs)
    wave_left = amplitude24bits * np.sin(2 * math.pi * frequency_left * samples)
    wave_right = amplitude24bits * np.sin(2 * math.pi * frequency_right * samples)

    if window_configuration:
        wave_left = generate_window(fs,
                                    wave_left,
                                    window_configuration.left_duration,
                                    window_configuration.left_apply_window_start,
                                    window_configuration.left_apply_window_end,
                                    window_configuration.left_window_function)
        wave_right = generate_window(fs,
                                     wave_right,
                                     window_configuration.right_duration,
                                     window_configuration.right_apply_window_start,
                                     window_configuration.right_apply_window_end,
                                     window_configuration.right_window_function)

    stereo = np.stack((wave_left, wave_right), axis=1)

    wave_int = stereo.astype(np.int32)

    if filename:
        with open(filename, 'wb') as f:
            wave_int.tofile(f)

    return wave_int.flatten()


def generate_window(fs, wave_int, duration, apply_start, apply_end, window_function):
    """

    :param fs: number of samples per second (standard)
    :param wave_int: base sound where the window will be applied
    :param duration: duration of the window (it will be the same on the start and end)
    :param apply_start: True if the window should be created at the start, False otherwise.
    :param apply_end: True if the window should be created at the end, False otherwise.
    :param window_function: window function to be generated. Possible values accepted:
        'Hanning', 'Hamming', 'Blackman', 'Bartlett'. It will revert to 'Hanning' if an unknown option is given.

    :return: Returns the modified sound with the window applied to it.
    """
    len_fade = int(duration * fs)
    if window_function == 'Hanning':
        fade_io = np.hanning(len_fade * 2)
    elif window_function == 'Hamming':
        fade_io = np.hamming(len_fade * 2)
    elif window_function == 'Blackman':
        fade_io = np.blackman(len_fade * 2)
    elif window_function == 'Bartlett':
        fade_io = np.bartlett(len_fade * 2)
    else:   # default
        fade_io = np.hanning(len_fade * 2)

    fadein = fade_io[:len_fade]
    fadeout = fade_io[len_fade:]
    win = np.ones(len(wave_int))
    if apply_start:
        win[:len_fade] = fadein
    if apply_end:
        win[-len_fade:] = fadeout
    wave_int = wave_int * win
    return wave_int

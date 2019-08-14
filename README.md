# Harp SoundCard TCP Server #

## Project information ##

This project makes available a set of functions and properties to allow the interaction with the Harp Sound Card through a TCP Server. The Harp Sound Card is a board developed by the Scientific Hardware Platform at the Champalimaud Foundation.

For more details regarding the Harp Sound Card please refer to the Wiki page on its Bitbucket page [here](https://bitbucket.org/fchampalimaud/device.soundcard/wiki/Home).

This project is maintained by the Scientific Software Platform at the Champalimaud Foundation.

## How to install ##

For Windows systems, go to the Releases page and download the latest compiled version.

## For developers ##

1. *(optional but recommended)* Create a Python virtual environment (e.g., with `conda` or `virtualenv` or another Python virtual environment manager)
2. Clone the repository to your local system

    `git clone https://github.com/fchampalimaud/soundcard_server.git`

3. Go to the `soundcard_server` folder just created and install the package in `develop` mode:

    `python setup.py develop` or by using `pip install -e .`

## Usage example ##

A Client Python example is available in the `examples` folder. There you can find several files to help you implement the Harp Protocol for the Sound Card if you develop in another language other than Python.

The `client.py` file has a client example. The file has some comments on how to use the Protocol API and the actions order. This works as an example and you might prefer to organize your code in another way.

The `protocol.py` file has the protocol implementation with some helper methods included.

The `tools.py` file has some utils functions to generate sinewave based sounds with support for window functions.

The messages format accepted by the Harp Sound Card TCP Server are described in detail in the Device.SoundCard Bitbucket repository [here](https://bitbucket.org/fchampalimaud/device.soundcard/src/master/TCP%20server%20protocol.txt).

## Feedback ##

Please use GitHub's issue system to submit feature suggestions, bug reports or to ask questions regarding the TCP server implementation.

For the Harp Sound Card inquiries please submit questions to the Bitbucket's page.

## License ##

The Harp Sound Card TCP server project uses the MIT license.

For details on the licenses used by the Harp Sound Card hardware device, please refer to the Bitbucket repository [here](https://bitbucket.org/fchampalimaud/device.soundcard/src/master/).

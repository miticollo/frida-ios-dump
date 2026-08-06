# frida-ios-dump
A tool for extracting decrypted IPA files from jailbroken devices.

## Installation

1. Install [frida](http://www.frida.re/) on your iOS device.
2. Install `npm` on your local machine:
   ```shell
   brew install node # MacOS homebrew
   pacman -S node npm # Arch Linux
   apt install nodejs npm # Debian et al.
   # for Windows, find a pre-built nodejs version at https://nodejs.org/en/download
   ```
3. Clone this project:
   ```shell
   git clone https://github.com/rec0de/frida-ios-dump.git
   cd frida-ios-dump
   ```
4. Create a virtual environment.
   ```shell
   python -m venv --upgrade-deps .venv
   source .venv/bin/activate
   ```
5. Run `pip install frida-tools --require-virtualenv` to install the Frida dependency.
6. Run the following command to install agent dependencies:
   ```shell
   cd agent
   npm install
   ```
7. Verify that the script works:
   ```shell
   cd ..
   python decrypter.py --version
   ```

## Usage

Connect your iOS device to your machine using a USB cable. (You can also decrypt iOS over Wireless using the remote communication provided by Frida, but USB is recommended) 

Make sure that you're in the python virtual environment:

```shell
cd frida-ios-dump
source .venv/bin/activate
``` 

Decrypt an already running app by its display name:

```shell
python ./decrypter.py -U -n Spotify 
```

Or launch and decrypt an app by its bundle identifier:

```shell
python ./decrypter.py -U -f com.google.ios.youtube
```

> [!NOTE]
> Launching apps with Frida via `-f` has [issues](https://github.com/frida/frida/issues/3484) with some versions of Dopamine (and possibly other jailbreaks) and may fail in strange ways.

## What's New?

This fork **no longer requires** using `scp`, unlike the original project. 
This is possible because I used the Frida [File API](https://frida.re/news/2022/07/06/frida-15-1-28-released/#:~:text=File%20API) to read all bytes inside a `Module` file and then parse it into a `MachO` object. 
Currently, this class does not implement all [Apple specifications](https://github.com/apple-oss-distributions/xnu/blob/main/EXTERNAL_HEADERS/mach-o/loader.h).

By doing this, the tool doesn't generate auxiliary files on the APFS filesystem, as they are only stored as `ArrayBuffer` (and [`node:Buffer`](https://nodejs.org/api/buffer.html)) in memory. 
After patching, I can send the file to PC/macOS using the [`send` Frida primitive](https://frida.re/docs/messages/).

Furthermore, this solution extends the [`ConsoleApplication`](https://github.com/frida/frida-tools/blob/1ea077fdb49440e5807cf25fae41e389e3d2bd4a/frida_tools/application.py#L124-L134) class, thereby avoiding issues with argument handling.

## Other Tools

You can decrypt apps that only run on recent iOS versions that you do not have a jailbreak for using a Mac with MacOS 11.2.3 or below (MacOS can be downgraded). See [UnFairPlay](https://github.com/subdiox/UnFairPlay) or [macOSAppstoreDecrypter](https://github.com/34306/macOSAppstoreDecrypter). [Dumpster](https://github.com/ChiChou/dumpster) can do the same on jailbroken iPhones.

## Further Reading

- [Decrypting iPhone Apps](https://sensepost.com/blog/2011/decrypting-iphone-apps/)
- [Decrypting iOS Binaries](https://mandalorianblog.wordpress.com/2013/05/03/decrypting-ios-binaries/)
- [Basic iOS Testing Operations](https://github.com/carlospolop/hacktricks/blob/master/mobile-pentesting/ios-pentesting/basic-ios-testing-operations.md#decryption-manual)
- [r2con 2016: iOS Reverse Engineering](https://github.com/radareorg/r2con2016/blob/master/talks/04-r2clutch/r2con-r2clutch.pdf)
- [r2flutch](https://github.com/as0ler/r2flutch)
- [frida-ios-dump by AloneMonkey](https://github.com/AloneMonkey/frida-ios-dump)
- [bagbak by ChiChou](https://github.com/ChiChou/bagbak)

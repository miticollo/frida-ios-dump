import os
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path
from threading import Thread
from typing import Any, Mapping, Optional, AnyStr, BinaryIO

import colorama
import frida
from colorama import Fore, Style
from frida_tools.application import ConsoleApplication
from frida_tools.stream_controller import StreamController
from frida_tools.units import bytes_to_megabytes

AGENT_ROOT_PATH: str = str(Path(__file__).parent.resolve() / "agent")


def main() -> None:
    app = DecrypterApplication()
    app.run()


class DecrypterApplication(ConsoleApplication):
    def __init__(self) -> None:
        self._script = None
        self._stream_controller = None
        self._time_started: Optional[float] = None
        self._failed_paths = []
        self._errors = 0
        self._tmpdir = None
        self._bundle_id = None
        self._version = None
        self._current_pull: Optional[str] = None

        super().__init__()

    def _usage(self) -> str:
        return "%(prog)s [options] target"

    def _needs_target(self) -> bool:
        return True

    def _start(self) -> None:
        try:
            self._update_status("Compiling script...")
            compiler: frida.Compiler = frida.Compiler()
            compiler.on("diagnostics", lambda diag: self._log(level="error", text=f"Compilation failed: {diag}"))
            agent_source: str = compiler.build('index.ts', project_root=AGENT_ROOT_PATH, compression='terser')
            self._update_status("Script compiled!")

            try:
                assert self._session is not None
                script = self._session.create_script(name="decrypter", source=agent_source, runtime=self._runtime)
                self._script = script
                script.on("message", self._process_message)
                self._on_script_created(script)

                self._tmpdir = tempfile.mkdtemp()
                self._local_path = Path(self._tmpdir) / "Payload"
                os.makedirs(self._local_path)

                self._resume()

                assert self._script is not None
                self._update_status("Injecting script...")
                script.load()
                self._update_status("Script injected!")

                self._stream_controller = StreamController(
                    self._post_stream_stanza,
                    self._on_incoming_stream_request,
                    on_incoming_stream_closed=self._on_incoming_stream_closed,
                    on_stats_updated=self._on_stream_stats_updated,
                )

                worker = Thread(target=self._perform_pull)
                worker.start()
                worker.join()

                assert (self._bundle_id and self._version) is not None

                print() # blank line
                self._update_status("Packaging into IPA... ")

                output_path = (Path(os.getcwd()) / f'{self._bundle_id}_{self._version}').name
                shutil.make_archive(output_path, 'zip', self._tmpdir, verbose=True)
                # Rename the .zip file to .ipa
                os.rename(output_path + ".zip", output_path + ".ipa")

                self._update_status(f"IPA saved @ ./{output_path}.ipa")

                shutil.rmtree(self._tmpdir)

                self._exit(0)
            except Exception as e:
                self.on_decrypt_stopped(str(e))
            except KeyboardInterrupt:
                self.on_decrypt_stopped()

        except Exception as e:
            self._log(level="error", text=f"Failed to decrypt: {e}")
            self._exit(1)
            return

    def _perform_pull(self) -> None:
        error = None
        try:
            assert self._script is not None
            self._script.exports_sync.dump()
        except Exception as e:
            error = e

        self._on_dump_finished(error)

    def _on_dump_finished(self, error: Optional[Exception]) -> None:
        for path, state in self._failed_paths:
            if state == "partial":
                try:
                    os.unlink(path)
                except:
                    pass

        if error is None:
            self._render_summary_ui()
        else:
            self._print_error(str(error))

        success = len(self._failed_paths) == 0 and error is None
        status = 0 if success else 1
        if status == 1:
            self._exit(status)

    def _render_progress_ui(self) -> None:
        assert self._stream_controller is not None
        self._print_progress(f"Pulling {self._current_pull}")

    def _render_summary_ui(self) -> None:
        assert self._time_started is not None
        duration = time.time() - self._time_started

        prefix = ""

        assert self._stream_controller is not None
        sc = self._stream_controller
        bytes_received = sc.bytes_received
        megabytes_per_second = bytes_to_megabytes(bytes_received) / duration

        self._print_progress(
            "{}{} file{} pulled. {:.1f} MB/s ({} bytes in {:.3f}s)".format(
                prefix,
                sc.streams_opened,
                "s" if sc.streams_opened != 1 else "",
                megabytes_per_second,
                bytes_received,
                duration,
            )
        )
        sys.stdout.write('\n')

    def _process_message(self, message: Mapping[Any, Any], data: bytes) -> None:
        handled = False

        message_type = message["type"]
        if message_type == "send":
            payload = message["payload"]
            ptype = payload["type"]
            if ptype == "stream":
                stanza = payload["payload"]
                assert self._stream_controller is not None
                self._stream_controller.receive(stanza, data)
                handled = True
            elif ptype == "pull:status":
                if self._time_started is None:
                    self._time_started = time.time()
                self._render_progress_ui()
                handled = True
            elif ptype == "pull:io-error":
                self._on_io_error(payload["path"], payload["remotePath"], payload["error"])
                handled = True
            elif ptype == "info":
                self._version = payload["version"]
                self._bundle_id = payload["bundleId"]
                handled = True
            elif ptype == "directory":
                os.makedirs(Path(self._local_path) / payload["path"])
                os.chmod(Path(self._local_path) / payload["path"],
                         stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                handled = True

        if not handled:
            self._print(message)

    def _on_io_error(self, remote_path, local_path, error) -> None:
        self._print_error(f"{remote_path}: {error}")
        self._failed_paths.append((local_path, "partial"))

    def _post_stream_stanza(self, stanza, data: Optional[AnyStr] = None) -> None:
        self._script.post({"type": "stream", "payload": stanza}, data=data)

    def _on_incoming_stream_request(self, label: str, details) -> BinaryIO:
        local_path = Path(self._local_path) / label
        try:
            self._current_pull = label
            return open(local_path, "w+b") # TODO: Not a good idea (e.g., main app binary is transferred twice)
        except Exception as e:
            self._print_error(str(e))
            self._failed_paths.append((local_path, "unopened"))
            raise

    def _on_incoming_stream_closed(self, label: str, details):
        mode: str = details["mode"]
        local_path = Path(self._local_path) / label
        if mode == "executable":
            os.chmod(local_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        else:
            os.chmod(local_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    def _on_stream_stats_updated(self) -> None:
        self._render_progress_ui()

    def _print_error(self, message: str) -> None:
        self._print(Fore.RED + Style.BRIGHT + message + Style.RESET_ALL, file=sys.stderr)

    def _print_step(self, message: str, **kwargs: Any) -> None:
        self._print(Style.BRIGHT + message + Style.RESET_ALL, **kwargs)

    def _print_progress(self, message: str) -> None:
        sys.stdout.write(colorama.ansi.clear_line() + colorama.ansi.CSI + '1' + 'G')
        sys.stdout.write(message)
        sys.stdout.flush()

    def on_decrypt_stopped(self, error_message: Optional[str] = None) -> None:
        if self._stream_controller is not None:
            self._stream_controller.dispose()
        if self._tmpdir is not None:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        if error_message is not None:
            self._log(level="error", text=error_message)
            self._exit(1)
        else:
            self._exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

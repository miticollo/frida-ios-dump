import os
import shutil
import stat
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Optional

import frida
from frida_tools.application import ConsoleApplication

AGENT_ROOT_PATH: str = str(Path(__file__).parent / 'agent')

# Start timer
start_time = time.time()


def main() -> None:
    app = DecrypterApplication()
    app.run()


class DecrypterApplication(ConsoleApplication):
    def __init__(self) -> None:
        self._script = None
        self._errors = 0
        self._tmpdir = tempfile.mkdtemp()
        self._payload = Path(self._tmpdir) / "Payload"
        self._bundle_id = None
        self._version = None

        super().__init__()

    def _usage(self) -> str:
        return "%(prog)s [options] target"

    def _needs_target(self) -> bool:
        return True

    def _start(self) -> None:
        try:
            self._update_status("Injecting script...")
            compiler: frida.Compiler = frida.Compiler()
            compiler.on("diagnostics", lambda diag: self._log(level="error", text=f"Compilation failed: {diag}"))
            agent_source: str = compiler.build('index.ts', project_root=AGENT_ROOT_PATH, compression='terser')

            try:
                assert self._session is not None
                script = self._session.create_script(name="decrypter", source=agent_source, runtime=self._runtime)
                self._script = script
                script.on("message", self._process_message)
                self._on_script_created(script)

                self._resume()

                os.makedirs(self._payload)

                script.load()

                output_path = (Path(os.getcwd()) / f'{self._bundle_id}_{self._version}').name
                shutil.make_archive(output_path, 'zip', self._tmpdir, verbose=True)
                # Rename the .zip file to .ipa
                os.rename(output_path + ".zip", output_path + ".ipa")

                shutil.rmtree(self._tmpdir)

                # End timer
                end_time = time.time()
                self._update_status(f'\n\nCompleted in {(end_time - start_time):.2f}s')

                self._exit(0)
            except Exception as e:
                self.on_decrypt_stopped(str(e))
            except KeyboardInterrupt:
                self.on_decrypt_stopped()

        except Exception as e:
            self._log(level="error", text=f"Failed to decrypt: {e}")
            self._exit(1)
            return

    def _process_message(self, message: Mapping[Any, Any], data: bytes) -> None:
        message_type = message["type"]
        if message_type == "error":
            text = message.get("stack", message["description"])
            self._log("error", text)
            self._errors += 1
            self._exit(1)
        elif message_type == "send":
            payload = message["payload"]
            mtype = payload["type"]
            if mtype == "file":
                with open(Path(self._payload) / payload["path"], "wb") as binary_file:
                    binary_file.write(data)
                if "mode" in payload and payload["mode"] == "executable":
                    os.chmod(Path(self._payload) / payload["path"],
                             stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                else:
                    os.chmod(Path(self._payload) / payload["path"],
                             stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            elif mtype == "directory":
                os.makedirs(Path(self._payload) / payload["path"])
                os.chmod(Path(self._payload) / payload["path"],
                         stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            elif mtype == "info":
                self._version = payload["version"]
                self._bundle_id = payload["bundleId"]
            else:
                self._print("message:", message, "data:", data)

    def on_decrypt_stopped(self, error_message: Optional[str] = None) -> None:
        shutil.rmtree(self._tmpdir)
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

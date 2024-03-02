import RemoteStreamController, { Packet } from 'frida-remote-stream';
import * as fs from 'node:fs';
import { Readable } from 'node:stream';
import { Buffer } from 'node:buffer';

const CHUNK_SIZE = 130_000_000; // about 123,98 MiB < 128 MiB

async function * toIterator(buffer: Buffer) {
    for (let b = 0; b < buffer.length; b+= CHUNK_SIZE)
        yield Buffer.from(buffer.subarray(b, Math.min(b + CHUNK_SIZE, buffer.length)));
}

export class Agent {
    #streamController = new RemoteStreamController();

    constructor() {
        recv(this.#onMessage);
        this.#streamController.events.on("send", this.#onStreamControllerSendRequest);
    }

    async pull_file(path: string, remotePath: string, mode: string): Promise<void> {
        await this.#pull(fs.createReadStream(path), remotePath, mode);
    }

    async pull_buffer(buffer: Buffer, remotePath: string, mode: string): Promise<void> {
        await this.#pull(Readable.from(toIterator(buffer)), remotePath, mode);
    }

    #pull = async (reader: Readable, remotePath: string, mode: string): Promise<void> => {
        send({
            type: "pull:status"
        });

        const writer = reader.pipe(this.#streamController.open(remotePath, {mode: mode}));

        const transfer = new Promise((resolve, reject) => {
            reader.addListener("error", onReaderError);
            writer.addListener("error", onWriterError);
            writer.addListener("finish", onWriterFinish);

            function onReaderError(error: Error): void {
                detachListeners();
                writer.end();
                reject(error);
            }

            function onWriterError(error: Error): void {
                detachListeners();
                reader.destroy();
                resolve(null);
            }

            function onWriterFinish(): void {
                detachListeners();
                resolve(null);
            }

            function detachListeners(): void {
                writer.removeListener("finish", onWriterFinish);
                writer.removeListener("error", onWriterError);
                reader.removeListener("error", onReaderError);
            }
        });

        try {
            await transfer;
        } catch (e) {
            send({
                type: "pull:io-error",
                path: "TODO", // TODO: replace this string with real path
                remotePath: remotePath,
                error: (e as Error).message
            });
        }
    }

    #onMessage = (message: any, rawData: ArrayBuffer | null): void => {
        const type: string = message.type;

        if (type === "stream") {
            const data: Buffer | null = (rawData !== null) ? Buffer.from(rawData) : null;
            this.#streamController.receive({
                stanza: message.payload,
                data
            });
        }

        recv(this.#onMessage);
    };

    #onStreamControllerSendRequest = (packet: Packet): void => {
        send({
            type: "stream",
            payload: packet.stanza
        }, packet.data?.buffer as ArrayBuffer);
    };
}
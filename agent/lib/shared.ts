import { NSBundle, NSFileManager } from "./types.js";
import ObjC from "frida-objc-bridge";

export const manager: ObjC.Object = NSFileManager["defaultManager"]();
export const appPath: ObjC.Object = NSBundle["mainBundle"]().bundlePath();
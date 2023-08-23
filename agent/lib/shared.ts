import { NSBundle, NSFileManager } from "./types.js";

export const manager: ObjC.Object = NSFileManager.defaultManager();
export const appPath: ObjC.Object = NSBundle.mainBundle().bundlePath();
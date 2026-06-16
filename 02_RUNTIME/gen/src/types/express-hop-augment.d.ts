import type { HopDispatchContext } from "./hop-types.js";

declare global {
  namespace Express {
    interface Request {
      hopDispatchContext?: HopDispatchContext;
    }
  }
}

export {};

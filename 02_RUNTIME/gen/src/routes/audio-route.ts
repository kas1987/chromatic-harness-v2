import { Router } from "express";
import path from "path";

export function createAudioRouter(audioDir: string): Router {
  const absAudioDir = path.resolve(audioDir);
  const router = Router();

  router.get("/:id", (req, res) => {
    const id = path.basename(req.params.id);
    // Validate: only alphanumeric+dash+underscore .wav files
    if (!/^[a-zA-Z0-9_-]+\.wav$/.test(id)) {
      return res.status(400).json({ error: "Invalid audio id" });
    }
    const filePath = path.join(absAudioDir, id);
    // Belt-and-suspenders: verify resolved path stays under absAudioDir
    if (!filePath.startsWith(absAudioDir + path.sep) && filePath !== absAudioDir) {
      return res.status(400).json({ error: "Invalid audio id" });
    }
    // Use sendFile callback to handle missing file gracefully (avoids TOCTOU)
    res.sendFile(filePath, (err) => {
      if (err && !res.headersSent) {
        res.status(404).json({ error: "Audio not found" });
      }
    });
  });

  return router;
}

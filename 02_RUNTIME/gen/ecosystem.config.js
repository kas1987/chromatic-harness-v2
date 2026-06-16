module.exports = {
  apps: [
    {
      name: "gen",
      script: "dist/index.js",
      cwd: "D:\\.04_Prism\\gen",
      env: {
        NODE_ENV: "development",
        // No GEN_TOKEN in dev — auth.ts skips auth when token is unset (localhost only)
        DATABASE_PATH: "./gen.db",
        GEN_PORT: "43123",
        // Disable unused services in dev
        GEN_COMFY_BRIDGE: "false",   // ComfyUI not always running
        GEN_ENABLE_OLLAMA: "false",  // enable manually when needed
        GEN_ENABLE_TTS: "false",     // TTS off by default in dev
      },
      restart_delay: 3000,
      max_restarts: 20,
      autorestart: true,
    },
  ],
};

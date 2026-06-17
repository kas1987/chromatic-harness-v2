import { initOtel } from "./otel/otel-init";
initOtel();

import { validateStartup } from "./core/startup-validation";
validateStartup();

import express, { Application, NextFunction, Request, Response } from "express";
import path from "path";
import fs from "fs";
import { authMiddleware } from "./middleware/auth";
import { hopMiddleware, initializeHopBroadcaster } from "./middleware/hop-middleware";
import { loggingMiddleware } from "./middleware/logging";
import {
  hooksRouter,
  initializeHooksRouter,
  initializeBudgetStore,
  initializeLlmRouting,
  initializeRoutingDecisionLog,
  initializeSkillDispatchRouter,
} from "./routes/hooks";
import { sessionRoutingStore } from "./routing/session-routing-store";
import { registerSessionRoutingStoreMetrics } from "./otel/meter";
import { config } from "./config";
import { MemoryStore } from "./memory/memory-store";
import { MemoryService } from "./memory/memory-service";
import { EmbeddingProvider } from "./memory/embedding-provider";
import { SimpleEmbeddingProvider } from "./memory/simple-embedding-provider";
import { adminRouter } from "./routes/admin-index";
import { initializeAdminMemoriesRouter } from "./routes/admin-memories";
import { initializeAdminBudgetRouter } from "./routes/admin-budget";
import { initializeAdminLearningRouter } from "./routes/admin-learning";
import { initializeAdminMaintenanceRouter } from "./routes/admin-maintenance";
import { initializeAdminMetaBrainRouter } from "./routes/admin-meta-brain";
import { initializeAdminGovernanceRouter } from "./routes/admin-governance";
import { isOfflineAuditEnabled } from "./routes/admin-modes";
import { AdminMemoryService } from "./services/admin-memory-service";
import { BudgetStore } from "./budget/budget-store";
import { LearningStore } from "./learning/learning-store";
import { MaintenanceStore } from "./maintenance/maintenance-store";
import { MetaBrainStore } from "./meta-brain/meta-brain-store";
import { runOfflineValueAudit } from "./maintenance/offline-value-audit";
import { AdaptiveRouter } from "./learning/adaptive-router";
import { LearningService } from "./learning/learning-service";
import { initializeLearningService, initializeOllamaEnricher, initializeTtsClient } from "./routes/hooks";
import { createWebhookChannelServices, webhooksRouter, channelsRouter } from "./routes/webhook-channel-index";
import { OllamaClient } from "./ollama/ollama-client";
import { OllamaEnricher } from "./ollama/ollama-enricher";
import { OllamaTriage } from "./ollama/ollama-triage";
import { ollamaRouter, initializeOllamaRouter } from "./routes/ollama-route";
import { TtsClient } from "./tts/tts-client";
import { createAudioRouter } from "./routes/audio-route";
import voiceRoles from "./tts/voice-roles.json";
import { ComfyEventBridge } from "./core/comfy-event-bridge";
import { comfyWebhooksRouter, initializeComfyWebhooksRouter } from "./routes/comfy-webhooks";
import Database from "better-sqlite3";
import { EventStore } from "./services/event-store";
import { ActionExecutor } from "./services/action-executor";
import { ingestRouter, initializeIngestRouter } from "./routes/ingest";
import { nateKnowledgeRouter } from "./routes/nate-knowledge";
import { getNateClient } from "./services/nate-client";
import { generationQueueRouter, initializeGenerationQueueRouter } from "./routes/generation-queue";
import { getGenerationQueueService } from "./services/generation-queue-service";
import { videoGenerationRouter, initializeVideoGenerationRouter } from "./routes/video-generation";
import { transparencyRouter } from "./routes/transparency-route";
import { injectAdapterRouter } from "./routes/inject-adapter";
import { delegateRouter, initializeDelegateRouter } from "./routes/delegate";
import { initializeSandboxOlRouter, sandboxOlRouter } from "./routes/sandbox-ol";

async function initializeApp() {
  const app: Application = express();
  let maintenanceRefreshInProgress = false;

  // Initialize memory store
  let memoryStore: MemoryStore;
  let memoryService: MemoryService;
  try {
    memoryStore = new MemoryStore(config.databasePath);
    console.log("Memory store initialized");

    // Initialize embeddings provider (simple by default, OpenAI if key provided)
    let embeddingProvider;
    if (config.enableEmbeddings && config.embeddingKey) {
      embeddingProvider = new EmbeddingProvider(config.embeddingKey, config.embeddingUrl, undefined, config.embeddingModel);
      console.log("OpenAI embeddings enabled");
    } else {
      embeddingProvider = new SimpleEmbeddingProvider();
      console.log("Using SimpleEmbeddingProvider for dev/test");
    }

    memoryService = new MemoryService(memoryStore, embeddingProvider);
    console.log("Memory service initialized");
  } catch (err) {
    console.error("Failed to initialize memory store/service:", err);
    throw err;
  }

  // Initialize admin services
  const adminMemoryService = new AdminMemoryService(config.databasePath);
  initializeAdminMemoriesRouter(adminMemoryService);

  const budgetDb = new Database(config.databasePath);
  const budgetStore = new BudgetStore(budgetDb);
  initializeAdminBudgetRouter(budgetStore);
  initializeBudgetStore(budgetDb);
  initializeRoutingDecisionLog(budgetDb);
  initializeDelegateRouter(budgetDb);
  initializeSandboxOlRouter(budgetDb);
  initializeSkillDispatchRouter(budgetDb);
  registerSessionRoutingStoreMetrics(() => sessionRoutingStore.getStats());

  // Initialize learning service
  const learningDb = new Database(config.databasePath);
  const learningStore = new LearningStore(learningDb);
  const adaptiveRouter = new AdaptiveRouter(learningStore);
  const learningService = new LearningService(learningStore, adaptiveRouter, getNateClient());
  initializeAdminLearningRouter(learningStore);
  initializeLearningService(learningService);

  // Initialize maintenance intelligence service
  const maintenanceDb = new Database(config.databasePath);
  const maintenanceStore = new MaintenanceStore(maintenanceDb);
  initializeAdminMaintenanceRouter(maintenanceStore);

  // Initialize governance + meta-brain service
  const metaBrainDb = new Database(config.databasePath);
  const metaBrainStore = new MetaBrainStore(metaBrainDb);
  initializeAdminMetaBrainRouter(metaBrainStore);
  initializeAdminGovernanceRouter(metaBrainStore);

  try {
    if (isOfflineAuditEnabled()) {
      void runOfflineValueAudit({
        sampleCount: Number(process.env.GEN_OFFLINE_AUDIT_SAMPLE_FILES || 6),
      }).catch((err) => {
        console.warn("[maintenance] Startup offline audit failed (fail-open):", err);
      });
    }
    const startupReview = maintenanceStore.ensureTodayReview("architecture", "architecture_director");
    maintenanceStore.exportDailyReviewArtifact("architecture", "architecture_director", startupReview.reviewDate);
    maintenanceStore.exportWeeklyIndependentRollupArtifact("architecture", "architecture_director", startupReview.reviewDate);
    console.log(`[maintenance] Daily Architecture Director review ensured for ${startupReview.reviewDate}`);
  } catch (err) {
    console.warn("[maintenance] Failed startup daily review generation (fail-open):", err);
  }

  setInterval(() => {
    void (async () => {
      if (maintenanceRefreshInProgress) {
        console.warn("[maintenance] Skipping refresh; prior run still in progress.");
        return;
      }
      maintenanceRefreshInProgress = true;
      try {
        if (isOfflineAuditEnabled()) {
          await runOfflineValueAudit({
            sampleCount: Number(process.env.GEN_OFFLINE_AUDIT_SAMPLE_FILES || 6),
          });
        }
        const review = maintenanceStore.ensureTodayReview("architecture", "architecture_director");
        maintenanceStore.exportDailyReviewArtifact("architecture", "architecture_director", review.reviewDate);
        maintenanceStore.exportWeeklyIndependentRollupArtifact("architecture", "architecture_director", review.reviewDate);
        console.log(`[maintenance] Daily review export refreshed for ${review.reviewDate}`);
      } catch (err) {
        console.warn("[maintenance] Scheduled daily review refresh failed (fail-open):", err);
      } finally {
        maintenanceRefreshInProgress = false;
      }
    })();
  }, 60 * 60 * 1000);

  // Initialize Ollama services
  let ollamaClientInstance: OllamaClient | undefined;
  let ollamaTriageInstance: OllamaTriage | undefined;
  let ollamaEnricherInstance: OllamaEnricher | undefined;
  if (config.enableOllama) {
    ollamaClientInstance = new OllamaClient(config.ollamaUrl);
    ollamaEnricherInstance = new OllamaEnricher(ollamaClientInstance, config.ollamaModel);
    ollamaTriageInstance = new OllamaTriage(ollamaClientInstance, config.ollamaModel);
    initializeOllamaEnricher(ollamaEnricherInstance);
    initializeOllamaRouter(ollamaClientInstance, ollamaTriageInstance);
    console.log(`Ollama enabled: ${config.ollamaUrl} model=${config.ollamaModel}`);
  } else {
    console.log("Ollama disabled (set GEN_ENABLE_OLLAMA=true to enable)");
  }

  if (config.enableGemma) {
    console.log(`Gemma (Ollama) enabled: ${config.ollamaUrl} model=${config.gemmaOllamaModel}`);
  } else {
    console.log("Gemma disabled (set GEN_ENABLE_GEMMA=true after ollama pull <tag>, e.g. gemma3:4b)");
  }

  // Initialize MiniMax client (optional, cloud-only provider)
  if (config.enableMiniMax) {
    const { MiniMaxClient } = await import("./minimax/minimax-client.js");
    const miniMaxInstance = new MiniMaxClient(config.miniMaxUrl, config.miniMaxModel, config.miniMaxApiKey);
    const available = await miniMaxInstance.isAvailable().catch(() => false);
    console.log(`MiniMax enabled: ${config.miniMaxUrl} model=${config.miniMaxModel} available=${available}`);
    if (!available) {
      console.warn("[minimax] Not available — run: ollama pull minimax-m2.5:cloud (or set GEN_MINIMAX_API_KEY for direct API)");
    }
  } else {
    console.log("MiniMax disabled (set GEN_ENABLE_MINIMAX=true to enable)");
  }

  initializeLlmRouting(budgetDb, ollamaClientInstance ?? null);
  if (ollamaClientInstance) {
    console.log("[llm-routing] LlmSelector + planning gate initialized");
  } else {
    console.log("[llm-routing] LlmSelector initialized (no Ollama — planning gate disabled)");
  }

  // Initialize ingest services
  const eventDb = new Database(config.databasePath);
  const eventStore = new EventStore(eventDb);
  const actionExecutor = new ActionExecutor({
    autoArchive: true,
    createTasksForActions: true,
    tasksOutputPath: `${config.synthesisOutputDir}/actions.jsonl`,
  });
  initializeIngestRouter(eventStore, ollamaTriageInstance ?? null, actionExecutor);
  console.log("Ingest service initialized");

  // Initialize generation queue service
  const queueDbPath = process.env.GEN_QUEUE_DB || ".agents/gen-queue.db";
  let queueService = null;
  try {
    queueService = getGenerationQueueService(queueDbPath);
    initializeGenerationQueueRouter(queueService);
    console.log(`[generation-queue] Queue service initialized → ${queueDbPath}`);
  } catch (err) {
    console.warn("[generation-queue] Failed to initialize queue service (fail-open):", err);
  }

  // Initialize TTS client (optional, fail-open)
  if (config.enableTts) {
    try {
      const absAudioDir = path.resolve(config.ttsAudioDir);
      await fs.promises.mkdir(absAudioDir, { recursive: true });
      const ttsClientInstance = new TtsClient(config.ttsUrl, absAudioDir, config.ttsTimeoutMs);

      initializeTtsClient(ttsClientInstance, ollamaClientInstance);

      // Non-blocking warmup (first request may be slow on cold TTS server)
      ttsClientInstance.warmup().catch((err: Error) =>
        console.warn("[tts] Model warmup failed (first request may be slow):", err.message)
      );

      // Hourly audio file cleanup
      setInterval(
        () => ttsClientInstance.pruneOldFiles().catch(console.warn),
        60 * 60 * 1000
      );

      // Startup voice validation (non-blocking, informational)
      ttsClientInstance.listVoices().then((available: string[]) => {
        const missing = Object.values(voiceRoles.roles as Record<string, string>)
          .filter((v) => !available.includes(v));
        if (missing.length) console.warn("[tts] Missing voice IDs in manifest:", missing);
        else console.log("[tts] All voice IDs validated.");
      }).catch((err: Error) =>
        console.warn("[tts] Voice validation skipped (TTS unavailable at startup):", err.message)
      );

      console.log(`[tts] TTS client enabled → ${config.ttsUrl}`);
    } catch (err) {
      console.warn("[tts] Failed to initialize TTS client:", err);
      // Fail open — server starts without TTS
    }
  }

  // Initialize Nate knowledge client (non-blocking, fail-open)
  getNateClient()
    .ping()
    .then((stats) => {
      if (stats) {
        console.log(
          `[nate-client] Nate client initialized — posts=${stats.posts} kits=${stats.kits} guides=${stats.guides}`,
        );
      } else {
        console.warn("[nate-client] Nate unavailable — knowledge queries will return empty results");
      }
    })
    .catch(() => {
      console.warn("[nate-client] Nate unavailable — knowledge queries will return empty results");
    });

  // Initialize webhook + channel services
  const { webhookStore, broadcaster } = createWebhookChannelServices(new Database(config.databasePath));
  void webhookStore; // used internally by routes
  initializeHopBroadcaster(broadcaster);

  // Initialize ComfyUI event bridge and webhook router (fail-open)
  let comfyBridge: ComfyEventBridge | null = null;
  if (config.enableComfyBridge) {
    comfyBridge = new ComfyEventBridge(config.comfyUrl, broadcaster, ollamaEnricherInstance);
    initializeComfyWebhooksRouter(comfyBridge);
  } else {
    initializeComfyWebhooksRouter(null as unknown as ComfyEventBridge);
  }

  // Initialize video generation router with queue and comfy bridge
  initializeVideoGenerationRouter(queueService, comfyBridge);

  // Initialize hooks router with memory service
  initializeHooksRouter(memoryService);

  // Middleware
  app.use(express.json());
  app.use(loggingMiddleware);

  // Health check endpoint (before auth, so it doesn't require token)
  app.get("/health", (req: Request, res: Response) => {
    res.json({ status: "ok" });
  });

  // Audio files served without auth (UUIDs are unguessable; 4h TTL via pruneOldFiles)
  app.use("/audio", createAudioRouter(path.resolve(config.ttsAudioDir)));

  // Auth required for all other routes
  app.use(authMiddleware);

  // Register routers
  app.use("/hooks", hopMiddleware);   // Hop: first-handler at dispatch entry point
  app.use("/hooks", hooksRouter);     // gen/ normal hook pipeline
  app.use("/webhooks", webhooksRouter);
  app.use("/channels", channelsRouter);
  app.use("/admin", adminRouter);
  app.use("/ollama", ollamaRouter);
  app.use("/ingest", ingestRouter);
  app.use("/nate", nateKnowledgeRouter);
  app.use("/generation/queue", generationQueueRouter);
  app.use("/api/video", videoGenerationRouter);
  app.use("/api/inject", injectAdapterRouter);
  app.use("/api/delegate", delegateRouter);
  app.use("/api/sandbox-ol", sandboxOlRouter);
  app.use("/comfy", comfyWebhooksRouter);
  app.use("/transparency", transparencyRouter);

  // Error handler (must have 4 params for Express to treat it as an error handler)
  app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
    console.error("Unhandled error:", err?.message ?? err);
    res.status(500).json({ error: "Internal server error" });
  });

  const PORT = process.env.GEN_PORT || config.port;
  const server = app.listen(PORT, () => {
    console.log(`Gen listening on port ${PORT}`);
    console.log(`Environment: ${config.nodeEnv}`);
    console.log(`Database: ${config.databasePath}`);

    if (comfyBridge) {
      comfyBridge.start();
      console.log(`[comfy-bridge] ComfyUI bridge initialized → ${config.comfyUrl}`);
    } else {
      console.log('[comfy-bridge] ComfyUI unavailable (optional)');
    }
  });

  // Graceful shutdown
  const gracefulShutdown = () => {
    console.log("\nShutting down gracefully...");
    comfyBridge?.stop();
    server.close(() => {
      console.log("Server closed");
    });
    memoryService.close();
    budgetDb.close();
    learningDb.close();
    maintenanceDb.close();
    metaBrainDb.close();
    eventDb.close();
    process.exit(0);
  };

  process.on("SIGINT", gracefulShutdown);
  process.on("SIGTERM", gracefulShutdown);

  return app;
}

initializeApp().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});

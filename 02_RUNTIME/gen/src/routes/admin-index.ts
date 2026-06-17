import { Router } from "express";
import { adminAuthMiddleware } from "../middleware/admin-auth";
import { adminMemoriesRouter } from "./admin-memories";
import { adminBudgetRouter } from "./admin-budget";
import { adminLearningRouter } from "./admin-learning";
import { adminMaintenanceRouter } from "./admin-maintenance";
import { adminMetaBrainRouter } from "./admin-meta-brain";
import { adminModesRouter } from "./admin-modes";
import { adminGovernanceRouter } from "./admin-governance";

export const adminRouter = Router();

adminRouter.use(adminAuthMiddleware);
adminRouter.use("/memories", adminMemoriesRouter);
adminRouter.use("/budget", adminBudgetRouter);
adminRouter.use("/learning", adminLearningRouter);
adminRouter.use("/maintenance", adminMaintenanceRouter);
adminRouter.use("/meta-brain", adminMetaBrainRouter);
adminRouter.use("/modes", adminModesRouter);
adminRouter.use("/governance", adminGovernanceRouter);

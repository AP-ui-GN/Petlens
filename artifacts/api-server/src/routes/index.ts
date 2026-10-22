import { Router, type IRouter } from "express";
import analyzeRouter from "./analyze";
import healthRouter from "./health";

const router: IRouter = Router();

router.use(healthRouter);
router.use(analyzeRouter);

export default router;

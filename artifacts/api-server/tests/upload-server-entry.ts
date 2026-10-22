/**
 * Bundled only by upload-cleanup.test.ts. This imports the real API app so the
 * upload integration test also exercises top-level security and CORS middleware.
 */

import app from "../src/app.ts";

export default app;

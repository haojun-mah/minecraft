package com.example.client;

public final class BuildState {

    public static final BuildState INSTANCE = new BuildState();

    private volatile boolean active = false;
    private volatile String  phase  = "";          // "generating" | "placing" | ""
    private volatile String  backendStage    = "";
    private volatile float   backendProgress = 0f;
    private volatile int     placed = 0;
    private volatile int     total  = 0;
    private volatile String  statusMessage = "";

    private BuildState() {}

    // -------------------------------------------------------------------------
    // State transitions

    public void startBackend() {
        active          = true;
        phase           = "generating";
        backendStage    = "queued";
        backendProgress = 0f;
        placed          = 0;
        total           = 0;
        statusMessage   = "Generating...";
    }

    public void updateBackend(String stage, float progress) {
        backendStage    = stage;
        backendProgress = progress;
        statusMessage   = stageLabel(stage);
    }

    public void startPlacement(int blockTotal) {
        phase         = "placing";
        total         = blockTotal;
        placed        = 0;
        statusMessage = "Placing...";
    }

    public void updatePlacement(int placedNow, int totalNow, boolean done) {
        placed = placedNow;
        total  = totalNow;
        if (done) {
            active        = false;
            phase         = "";
            statusMessage = "Done! Placed " + totalNow + " blocks.";
        } else {
            statusMessage = "Placing... " + placedNow + "/" + totalNow;
        }
    }

    public void setError(String message) {
        active        = false;
        phase         = "";
        statusMessage = message;
    }

    public void clear() {
        active          = false;
        phase           = "";
        backendStage    = "";
        backendProgress = 0f;
        placed          = 0;
        total           = 0;
        statusMessage   = "";
    }

    // -------------------------------------------------------------------------
    // Reads

    public boolean isActive()          { return active; }
    public String  getPhase()          { return phase; }
    public String  getBackendStage()   { return backendStage; }
    public float   getBackendProgress(){ return backendProgress; }
    public int     getPlaced()         { return placed; }
    public int     getTotal()          { return total; }
    public String  getStatusMessage()  { return statusMessage; }

    public float getOverallProgress() {
        if ("placing".equals(phase) && total > 0)
            return (float) placed / total;
        return backendProgress;
    }

    // -------------------------------------------------------------------------

    private static String stageLabel(String stage) {
        return switch (stage) {
            case "research"     -> "Researching...";
            case "planning"     -> "Planning...";
            case "image_gen"    -> "Generating image...";
            case "image_to_3d"  -> "Building 3D model...";
            case "voxelizing"   -> "Voxelizing...";
            case "block_mapping"-> "Mapping blocks...";
            case "encoding"     -> "Finishing...";
            default             -> "Generating...";
        };
    }
}

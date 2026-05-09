package com.example.client;

import com.example.network.BuildBlockEntry;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.fabricmc.fabric.api.client.rendering.v1.level.LevelRenderContext;
import net.fabricmc.fabric.api.client.rendering.v1.level.LevelRenderEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.ShapeRenderer;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

import java.util.ArrayList;
import java.util.List;

/**
 * Purely client-side ghost preview — no blocks placed on the server.
 * Active when the ArchitectScreen is closed; origin follows the crosshair.
 * While the screen is open, origin is controlled by the coordinate fields.
 */
public final class GhostPreview {

    // Relative offsets from origin for each block in the shape
    private static final List<int[]> OFFSETS = new ArrayList<>();
    private static BlockPos origin = BlockPos.ZERO;
    private static boolean active = false;

    private GhostPreview() {}

    // -------------------------------------------------------------------------
    // State API (called from ArchitectScreen)

    public static void setShape(List<BuildBlockEntry> blocks) {
        OFFSETS.clear();
        if (blocks.isEmpty()) { active = false; return; }
        int minX = Integer.MAX_VALUE, minY = Integer.MAX_VALUE, minZ = Integer.MAX_VALUE;
        for (BuildBlockEntry b : blocks) {
            minX = Math.min(minX, b.x());
            minY = Math.min(minY, b.y());
            minZ = Math.min(minZ, b.z());
        }
        for (BuildBlockEntry b : blocks) {
            OFFSETS.add(new int[]{b.x() - minX, b.y() - minY, b.z() - minZ});
        }
        active = true;
    }

    public static void setOrigin(BlockPos pos) { origin = pos; }
    public static BlockPos getOrigin()         { return origin; }
    public static boolean isActive()           { return active; }
    public static void clear()                 { active = false; OFFSETS.clear(); }

    // -------------------------------------------------------------------------
    // Tick — runs every client tick; when no screen is open the ghost follows
    // the player's crosshair so it feels like "drag-and-drop" positioning.

    public static void tick(Minecraft mc) {
        if (!active || mc.player == null || mc.screen != null) return;
        if (mc.hitResult instanceof BlockHitResult bhr
                && bhr.getType() != HitResult.Type.MISS) {
            origin = bhr.getBlockPos().relative(bhr.getDirection());
        }
    }

    // -------------------------------------------------------------------------
    // Render — registered on BEFORE_GIZMOS; draws wireframe outlines in world

    public static void render(LevelRenderContext ctx) {
        if (!active || OFFSETS.isEmpty()) return;

        // Camera position for this frame
        var cam = Minecraft.getInstance().gameRenderer.getMainCamera().position();
        double camX = cam.x, camY = cam.y, camZ = cam.z;

        PoseStack ps     = ctx.poseStack();
        MultiBufferSource.BufferSource bufs = ctx.bufferSource();
        VertexConsumer vc = bufs.getBuffer(RenderTypes.LINES);
        VoxelShape block  = Shapes.block();

        for (int[] off : OFFSETS) {
            double wx = origin.getX() + off[0] - camX;
            double wy = origin.getY() + off[1] - camY;
            double wz = origin.getZ() + off[2] - camZ;
            ShapeRenderer.renderShape(ps, vc, block, wx, wy, wz, 0x55FF55, 1.0f);
        }

        bufs.endBatch(RenderTypes.LINES);
    }

    // -------------------------------------------------------------------------
    // Registration — call once from ExampleModClient.onInitializeClient()

    public static void register() {
        LevelRenderEvents.BEFORE_GIZMOS.register(GhostPreview::render);
    }
}

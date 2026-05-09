package com.example.client;

import com.example.network.BuildBlockEntry;
import com.mojang.blaze3d.vertex.PoseStack;
import net.fabricmc.fabric.api.client.rendering.v1.level.LevelRenderContext;
import net.fabricmc.fabric.api.client.rendering.v1.level.LevelRenderEvents;
import net.minecraft.client.Minecraft;
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
 * Client-side ghost preview rendered via MC 26.1.2 submitCustomGeometry API.
 * No server blocks placed — walk-through by default.
 * While a screen is open, origin is pinned to the coordinate fields.
 * While no screen is open, origin follows the crosshair each tick.
 */
public final class GhostPreview {

    private static final List<int[]> OFFSETS = new ArrayList<>();
    private static BlockPos origin = BlockPos.ZERO;
    private static boolean active = false;

    private GhostPreview() {}

    // -------------------------------------------------------------------------
    // State API

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
    // Tick — crosshair follow when no screen is open

    public static void tick(Minecraft mc) {
        if (!active || mc.player == null || mc.screen != null) return;
        if (mc.hitResult instanceof BlockHitResult bhr
                && bhr.getType() != HitResult.Type.MISS) {
            origin = bhr.getBlockPos().relative(bhr.getDirection());
        }
    }

    // -------------------------------------------------------------------------
    // Render — MC 26.1.2: submitCustomGeometry via COLLECT_SUBMITS

    public static void render(LevelRenderContext ctx) {
        if (!active || OFFSETS.isEmpty()) return;

        var cam = Minecraft.getInstance().gameRenderer.getMainCamera().position();
        double camX = cam.x, camY = cam.y, camZ = cam.z;

        VoxelShape blockShape = Shapes.block();

        ctx.submitNodeCollector().submitCustomGeometry(
            new PoseStack(),
            RenderTypes.LINES,
            (pose, vc) -> {
                PoseStack ps = new PoseStack();
                ps.last().set(pose);
                for (int[] off : OFFSETS) {
                    double wx = origin.getX() + off[0] - camX;
                    double wy = origin.getY() + off[1] - camY;
                    double wz = origin.getZ() + off[2] - camZ;
                    ps.pushPose();
                    ps.translate(wx, wy, wz);
                    ShapeRenderer.renderShape(ps, vc, blockShape, 0.0, 0.0, 0.0, 0x55FF55, 1.0f);
                    ps.popPose();
                }
            }
        );
    }

    // -------------------------------------------------------------------------
    // Registration

    public static void register() {
        LevelRenderEvents.COLLECT_SUBMITS.register(GhostPreview::render);
    }
}

const std = @import("std");

const MEMORY_BYTES = 64 * 1024 * 1024;

// BFS buffer size used by the wasm depth allocation, in Boards (8 bytes each).
// The console build exposes the same knob as `-b`; this makes the web build
// configurable too instead of a constant buried in src/wasm/main.zig.
const DEFAULT_BUDGET = 655360;

pub fn build(b: *std.Build) void {
  const target = b.standardTargetOptions(.{});
  const optimize = b.standardOptimizeOption(.{});
  const strip = optimize == .fast or optimize == .small;

  const budget = b.option(u32, "budget", "BFS buffer size for the wasm build, in Boards") orelse DEFAULT_BUDGET;
  // Transposition table size (log2 entries) for the *console* build. The web
  // build keeps its own constant in ParallelSearch.zig; this exists so a
  // benchmark can match the wasm's table (20) instead of the CLI default (18).
  const cache_bits = b.option(u6, "cache", "Transposition table bits for the console build") orelse 18;

  const utils = b.addModule("utils", .{
    .root_source_file = b.path("src/utils/main.zig"),
  });

  const engine = b.addModule("engine", .{
    .root_source_file = b.path("src/engine/main.zig"),
    .imports = &.{
      .{
        .name = "utils",
        .module = utils,
      },
    },
  });

  const imports = [_]std.Build.Module.Import{
    .{
      .name = "engine",
      .module = engine,
    },
    .{
      .name = "utils",
      .module = utils,
    },
  };

  const main_exe = b.addExecutable(.{
    .name = "2048",
    .root_module = b.createModule(.{
      .root_source_file = b.path("src/cli/main.zig"),
      .target = target,
      .optimize = optimize,
      .strip = strip,
      .imports = &imports,
    }),
  });

  b.installArtifact(main_exe);

  const cli_options = b.addOptions();
  cli_options.addOption(u6, "cache_bits", cache_bits);
  main_exe.root_module.addOptions("build_options", cli_options);

  const main_cmd = b.addRunArtifact(main_exe);
  main_cmd.step.dependOn(b.getInstallStep());

  main_cmd.addPassthruArgs();

  const main_run = b.step("run", "Run the main application");
  main_run.dependOn(&main_cmd.step);

  const wasm_target = b.resolveTargetQuery(.{
    .cpu_arch = .wasm32,
    .os_tag = .freestanding,
    .cpu_features_add = std.Target.wasm.featureSet(&.{
      .atomics,
      .bulk_memory,
      .extended_const,
      .multivalue,
      .nontrapping_fptoint,
      .sign_ext,
      .simd128,
      .tail_call,
    }),
  });

  const wasm_main = b.addExecutable(.{
    .name = "main",
    .root_module = b.createModule(.{
      .root_source_file = b.path("src/wasm/main.zig"),
      .target = wasm_target,
      .optimize = optimize,
      .strip = strip,
      .imports = &imports,
    }),
  });

  const wasm_options = b.addOptions();
  wasm_options.addOption(u32, "budget", budget);
  wasm_main.root_module.addOptions("build_options", wasm_options);

  wasm_main.rdynamic = true;
  wasm_main.entry = .disabled;

  wasm_main.shared_memory = true;
  wasm_main.import_memory = true;
  wasm_main.initial_memory = MEMORY_BYTES;
  wasm_main.max_memory = MEMORY_BYTES;
  const bin = wasm_main.getEmittedBin();
  const artifact = b.addInstallFile(bin, "main.wasm");

  b.getInstallStep().dependOn(&artifact.step);
}

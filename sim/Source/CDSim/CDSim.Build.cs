// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

using UnrealBuildTool;

public class CDSim : ModuleRules
{
	public CDSim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// Flat per-folder layout (Core/, World/, Vehicle/, ...) with no
		// Public/Private split: expose the module root so that includes are
		// written as "Vehicle/CDSimVehiclePawn.h" both here and in platform
		// plugins that depend on this module.
		PublicIncludePaths.Add(ModuleDirectory);

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"Json",
			"JsonUtilities",
			"NetCore",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Sockets",
			"Networking",
			"HTTP",
			"HeadMountedDisplay",
		});
	}
}

// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

using UnrealBuildTool;

public class CDSimPlatform_cdpl_quad_01 : ModuleRules
{
	public CDSimPlatform_cdpl_quad_01(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicIncludePaths.Add(ModuleDirectory);

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			// The CD Sim core game module: provides UCDSimPlatformVisualsComponent,
			// FCDSimPlatformVisualsRegistry and FCDSimPlatformSpec. A project plugin
			// depending on the project's primary module is intentional here; if UBT
			// ever rejects it, move the shared platform API into a "CDSimCore"
			// plugin (see docs/BUILDING_UE5.md, Troubleshooting). Public because
			// CDSimQuad01Visuals.h derives from a CDSim class.
			"CDSim",
		});
	}
}

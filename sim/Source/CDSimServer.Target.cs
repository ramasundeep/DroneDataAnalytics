// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// Dedicated server for fleet mode (docs/ADR/0010, Phase 5). Run headless with -nullrhi.

using UnrealBuildTool;
using System.Collections.Generic;

public class CDSimServerTarget : TargetRules
{
	public CDSimServerTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Server;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
		ExtraModuleNames.Add("CDSim");
	}
}

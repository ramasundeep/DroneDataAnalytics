// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// Editor build used by engineers to open and PIE the project.

using UnrealBuildTool;
using System.Collections.Generic;

public class CDSimEditorTarget : TargetRules
{
	public CDSimEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
		ExtraModuleNames.Add("CDSim");
	}
}

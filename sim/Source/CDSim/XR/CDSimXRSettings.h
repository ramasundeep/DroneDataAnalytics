// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include "CDSimXRSettings.generated.h"

/**
 * VR is a project CONFIGURATION, not a fork (docs/ADR/0011).
 *
 * The same binary runs desktop or VR. XR is enabled when EITHER
 *   - the console variable `cdsim.XR.Enable` is 1
 *     (Config/DefaultEngine.ini [ConsoleVariables], -DPCVars=cdsim.XR.Enable=1,
 *      or `cdsim.XR.Enable 1` in the console), OR
 *   - the process was launched with -vr (the engine's own VR switch; we
 *     mirror it into the cvar so gameplay code has one place to ask).
 * Default is desktop: the OpenXR plugin loads but stereo stays off.
 *
 * TODO(Phase 5): VR pawn / motion-controller input, comfort options, and a
 * VR-specific scalability profile (docs/10_ROADMAP.md).
 */
UCLASS()
class CDSIM_API UCDSimXRSettings : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Name of the console variable. */
	static const TCHAR* CVarName;

	/** True if this run is in the VR configuration. */
	UFUNCTION(BlueprintPure, Category = "CDSim|XR")
	static bool IsXREnabled();

	/**
	 * Resolve -vr / cvar at game start and switch the HMD on or off to match.
	 * Called from UCDSimGameInstance::OnStart. Safe with no headset attached.
	 */
	UFUNCTION(BlueprintCallable, Category = "CDSim|XR")
	static void ApplyStartupXRMode();
};

// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"

/**
 * Platform plugin module for cdpl_quad_01. On startup it registers this
 * platform's visuals component with the CD Sim core
 * (FCDSimPlatformVisualsRegistry), so ACDSimVehiclePawn uses
 * UCDSimQuad01Visuals whenever a session spawns platform "cdpl_quad_01".
 *
 * Physics, sensors and failure modes come from platforms/cdpl_quad_01/platform.yaml,
 * not from this plugin: the plugin is visuals + part anchors only.
 */
class FCDSimPlatformQuad01Module : public IModuleInterface
{
public:
	static const FName PlatformId;

	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};

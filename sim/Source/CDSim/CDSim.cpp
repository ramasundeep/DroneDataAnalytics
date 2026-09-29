// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "CDSim.h"

#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogCDSim);

/**
 * Primary game module for CD Sim. The core (world, physics, vehicle,
 * recording) lives here; vehicles are data (platforms/<id>/platform.yaml)
 * plus an optional CDSimPlatform_<id> plugin for visuals.
 */
class FCDSimModule : public FDefaultGameModuleImpl
{
public:
	virtual void StartupModule() override
	{
		UE_LOG(LogCDSim, Log, TEXT("CD Sim core module starting (UNVERIFIED BUILD - see docs/BUILDING_UE5.md)."));
	}

	virtual void ShutdownModule() override
	{
		UE_LOG(LogCDSim, Log, TEXT("CD Sim core module shutting down."));
	}
};

IMPLEMENT_PRIMARY_GAME_MODULE(FCDSimModule, CDSim, "CDSim");

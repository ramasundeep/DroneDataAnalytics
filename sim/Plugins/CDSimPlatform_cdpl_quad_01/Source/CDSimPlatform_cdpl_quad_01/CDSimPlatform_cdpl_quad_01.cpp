// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "CDSimPlatform_cdpl_quad_01.h"

#include "Modules/ModuleManager.h"
#include "UObject/SoftObjectPath.h"
#include "Vehicle/CDSimPlatformVisualsComponent.h"

const FName FCDSimPlatformQuad01Module::PlatformId(TEXT("cdpl_quad_01"));

void FCDSimPlatformQuad01Module::StartupModule()
{
	// Registered by class path (not StaticClass()) so this is safe regardless of
	// UObject initialisation order; the pawn resolves it when spawning.
	FCDSimPlatformVisualsRegistry::Register(
		PlatformId, FSoftClassPath(TEXT("/Script/CDSimPlatform_cdpl_quad_01.CDSimQuad01Visuals")));
}

void FCDSimPlatformQuad01Module::ShutdownModule()
{
	FCDSimPlatformVisualsRegistry::Unregister(PlatformId);
}

IMPLEMENT_MODULE(FCDSimPlatformQuad01Module, CDSimPlatform_cdpl_quad_01);

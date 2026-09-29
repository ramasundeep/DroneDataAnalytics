// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Vehicle/CDSimPlatformVisualsComponent.h"

#include "CDSimQuad01Visuals.generated.h"

class UStaticMeshComponent;

/**
 * Placeholder look for CDPL Quad 01, built from /Engine/BasicShapes (Cube,
 * Cylinder): body box, battery, four arms, motors, propeller discs and GPS mast,
 * all positioned from platform.yaml (actuator positions, part offsets) — not
 * hard-coded — so the placeholder tracks the YAML.
 *
 * Part anchors (socket stand-ins) created, matching platform.yaml
 * maintenance.parts[].anchor.socket:
 *   SOCKET_Prop_M1, SOCKET_Prop_M2, SOCKET_Prop_M3, SOCKET_Prop_M4,
 *   SOCKET_Motor_M2, SOCKET_Battery
 * plus ANCHOR_<part_id> for parts anchored by offset_m (e.g. ANCHOR_gps_mast).
 *
 * When CAD arrives (docs/04_PLATFORM_PLUGIN_SPEC.md), replace BuildVisuals
 * with a single static mesh carrying sockets of the same names.
 * TODO(Phase 6): maintainer-module interaction on these anchors (docs/10_ROADMAP.md).
 */
UCLASS(ClassGroup = (CDSim), meta = (BlueprintSpawnableComponent))
class CDSIMPLATFORM_CDPL_QUAD_01_API UCDSimQuad01Visuals : public UCDSimPlatformVisualsComponent
{
	GENERATED_BODY()

public:
	virtual void BuildVisuals(const FCDSimPlatformSpec& Spec) override;
	virtual void UpdateActuatorVisuals(const TArray<double>& NormalisedOutputs) override;

private:
	/** Propeller discs in spec actuator order, spun by UpdateActuatorVisuals. */
	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> PropellerMeshes;

	/** +1 for CCW, -1 for CW, spec order. */
	TArray<double> SpinSigns;
};

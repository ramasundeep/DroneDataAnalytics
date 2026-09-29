// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Sensors/CDSimSensorComponent.h"

#include "CDSimDownCameraComponent.generated.h"

class USceneCaptureComponent2D;
class UTextureRenderTarget2D;

/**
 * Camera sensor (platform.yaml `type: camera`, e.g. cam_down) wrapping a
 * USceneCaptureComponent2D. Params: width_px, height_px, hfov_deg. Captures
 * on demand at rate_hz (bCaptureEveryFrame = false) so cost is bounded.
 *
 * Not created on a dedicated server (no renderer, -nullrhi).
 * TODO(Phase 7): read back frames for labelled-data export and RL
 * observations; lens distortion and noise (docs/10_ROADMAP.md).
 */
UCLASS(ClassGroup = (CDSim), meta = (BlueprintSpawnableComponent))
class CDSIM_API UCDSimDownCameraComponent : public UCDSimSensorComponent
{
	GENERATED_BODY()

public:
	virtual void ConfigureFromSpec(const FCDSimSensorSpec& InSpec, int32 NoiseSeed) override;

	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	UTextureRenderTarget2D* GetRenderTarget() const { return RenderTarget; }

protected:
	virtual void Sample(int64 SimTimeUs, const FCDSimRigidBodyState& Truth) override;

	UPROPERTY(VisibleInstanceOnly, Transient, Category = "CDSim|Sensor")
	TObjectPtr<USceneCaptureComponent2D> Capture;

	UPROPERTY(VisibleInstanceOnly, Transient, Category = "CDSim|Sensor")
	TObjectPtr<UTextureRenderTarget2D> RenderTarget;
};

// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Sensors/CDSimDownCameraComponent.h"

#include "CDSim.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "GameFramework/Actor.h"
#include "Vehicle/CDSimRigidBody.h"

void UCDSimDownCameraComponent::ConfigureFromSpec(const FCDSimSensorSpec& InSpec, int32 NoiseSeed)
{
	Super::ConfigureFromSpec(InSpec, NoiseSeed);

	if (IsRunningDedicatedServer())
	{
		return; // No renderer on the fleet server.
	}

	const int32 Width = FMath::Max(16, FMath::RoundToInt(Spec.GetParam(TEXT("width_px"), 640.0f)));
	const int32 Height = FMath::Max(16, FMath::RoundToInt(Spec.GetParam(TEXT("height_px"), 480.0f)));
	const float HfovDeg = Spec.GetParam(TEXT("hfov_deg"), 78.0f);

	RenderTarget = NewObject<UTextureRenderTarget2D>(this, TEXT("CameraRenderTarget"));
	RenderTarget->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA8;
	RenderTarget->InitAutoFormat(Width, Height);
	RenderTarget->UpdateResourceImmediate(true);

	Capture = NewObject<USceneCaptureComponent2D>(GetOwner(), *FString::Printf(TEXT("%s_Capture"), *Spec.Id.ToString()));
	Capture->SetupAttachment(this);
	Capture->FOVAngle = HfovDeg;
	Capture->TextureTarget = RenderTarget;
	Capture->bCaptureEveryFrame = false;
	Capture->bCaptureOnMovement = false;
	Capture->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	Capture->RegisterComponent();

	UE_LOG(LogCDSim, Log, TEXT("Camera '%s': %dx%d, hfov %.1f deg, %.1f Hz."), *Spec.Id.ToString(), Width, Height,
		HfovDeg, Spec.RateHz);
}

void UCDSimDownCameraComponent::Sample(int64 /*SimTimeUs*/, const FCDSimRigidBodyState& /*Truth*/)
{
	if (Capture != nullptr)
	{
		// Captures on the next render. TODO(Phase 7): stamp the frame with SimTimeUs on readback.
		Capture->CaptureSceneDeferred();
	}
}

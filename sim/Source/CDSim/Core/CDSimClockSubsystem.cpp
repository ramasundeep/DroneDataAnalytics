// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Core/CDSimClockSubsystem.h"

#include "CDSim.h"
#include "Engine/World.h"

void UCDSimClockSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	SimTimeUs = 0;
	StepCount = 0;
	AccumulatorUs = 0.0;
	bRunning = false; // Starts paused, like cdsim_common.simclock.SimClock.
	UE_LOG(LogCDSim, Log, TEXT("Sim clock initialised: %lld us step (%.0f Hz), paused."), PhysicsStepUs,
		1.0e6 / static_cast<double>(PhysicsStepUs));
}

void UCDSimClockSubsystem::Deinitialize()
{
	OnPhysicsStep.Clear();
	Super::Deinitialize();
}

bool UCDSimClockSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	// Only real sessions get a clock; editor preview worlds do not.
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UCDSimClockSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UCDSimClockSubsystem, STATGROUP_Tickables);
}

void UCDSimClockSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	if (!bRunning || Mode != ECDSimClockMode::Realtime)
	{
		return;
	}

	// Bank frame time at the current rate. Because the rate only scales what
	// is added from now on, changing it never makes sim time jump.
	AccumulatorUs += static_cast<double>(DeltaTime) * 1.0e6 * static_cast<double>(SimRate);

	int32 StepsThisFrame = 0;
	while (AccumulatorUs >= static_cast<double>(PhysicsStepUs) && StepsThisFrame < MaxStepsPerFrame)
	{
		AccumulatorUs -= static_cast<double>(PhysicsStepUs);
		AdvanceOneStep();
		++StepsThisFrame;
	}

	if (StepsThisFrame == MaxStepsPerFrame && AccumulatorUs >= static_cast<double>(PhysicsStepUs))
	{
		// We cannot keep up: drop the backlog rather than freeze the game
		// thread. Sim time stays monotonic; it just runs slower than wall-clock.
		UE_LOG(LogCDSim, Warning, TEXT("Sim clock behind real time; dropping %.0f us of backlog."), AccumulatorUs);
		AccumulatorUs = 0.0;
	}
}

void UCDSimClockSubsystem::Resume()
{
	bRunning = true;
}

void UCDSimClockSubsystem::Pause()
{
	bRunning = false;
}

void UCDSimClockSubsystem::SetSimRate(float NewRate)
{
	const float Clamped = FMath::Clamp(NewRate, MinRate, MaxRate);
	if (!FMath::IsNearlyEqual(Clamped, NewRate))
	{
		UE_LOG(LogCDSim, Warning, TEXT("Sim rate %.3f outside [%.1f, %.1f]; clamped to %.3f."), NewRate, MinRate,
			MaxRate, Clamped);
	}
	SimRate = Clamped;
}

void UCDSimClockSubsystem::SetMode(ECDSimClockMode NewMode)
{
	if (Mode != NewMode)
	{
		Mode = NewMode;
		AccumulatorUs = 0.0;
	}
}

int64 UCDSimClockSubsystem::Step(int32 Ticks)
{
	if (Mode != ECDSimClockMode::Stepped)
	{
		UE_LOG(LogCDSim, Warning, TEXT("Step() is only valid on a Stepped clock; ignored."));
		return SimTimeUs;
	}
	for (int32 Index = 0; Index < FMath::Max(Ticks, 0); ++Index)
	{
		AdvanceOneStep();
	}
	return SimTimeUs;
}

void UCDSimClockSubsystem::AdvanceOneStep()
{
	SimTimeUs += PhysicsStepUs;
	++StepCount;
	OnPhysicsStep.Broadcast(SimTimeUs, PhysicsStepUs);
}

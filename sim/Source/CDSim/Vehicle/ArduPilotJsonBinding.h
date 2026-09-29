// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "Vehicle/CDSimPhysicsBinding.h"

#include "ArduPilotJsonBinding.generated.h"

class FInternetAddr;
class FSocket;

/**
 * ArduPilot SITL "JSON" physics backend (unmodified ArduPilot, `-f JSON` /
 * `--model JSON`), per docs/05_SITL_INTEGRATION.md and docs/ADR/0003.
 *
 * Wire protocol (UDP; we bind the port, SITL sends to it and we reply to the
 * sender address):
 *
 *   SITL -> CD Sim, binary little-endian servo packet, either
 *     16 ch: uint16 magic = 18458; uint16 frame_rate; uint32 frame_count; uint16 pwm[16]   (40 bytes)
 *     32 ch: uint16 magic = 29569; uint16 frame_rate; uint32 frame_count; uint16 pwm[32]   (72 bytes)
 *
 *   CD Sim -> SITL, one JSON object, preceded AND terminated by "\n":
 *     {"timestamp": <s>,
 *      "imu": {"gyro": [p, q, r], "accel_body": [ax, ay, az]},
 *      "position": [n, e, d], "attitude": [roll, pitch, yaw], "velocity": [vn, ve, vd]}
 *
 * Frames: ArduPilot uses NED world / FRD body, metres, radians — exactly what
 * the pawn's physics state already uses, so no conversion happens here. The
 * NED <-> UE (cm, left-handed X fwd / Y right / Z up) conversion lives in
 * Core/CDSimFrames.h and is applied only when placing the actor in the world.
 *
 * TODO(Phase 1): true lock-step (clock in Stepped mode, one physics step per
 * servo frame, SITL speed-up) — today the pawn polls this binding once per
 * 400 Hz step and SITL is expected to run with SIM_RATE_HZ=400. See
 * docs/10_ROADMAP.md Phase 1 acceptance (deterministic replay).
 */
UCLASS()
class CDSIM_API UArduPilotJsonBinding : public UObject, public ICDSimPhysicsBinding
{
	GENERATED_BODY()

public:
	static constexpr uint16 Magic16 = 18458;
	static constexpr uint16 Magic32 = 29569;
	static constexpr int32 DefaultPort = 9002;
	static constexpr uint16 PwmMin = 1000;
	static constexpr uint16 PwmMax = 2000;

	/** Must be set before StartBinding(). */
	void SetListenPort(int32 InPort) { ListenPort = InPort; }

	// ICDSimPhysicsBinding
	virtual bool StartBinding() override;
	virtual void StopBinding() override;
	virtual bool ReceiveActuatorCommands(TArray<float>& OutNormalised) override;
	virtual void SendSensorState(const FCDSimAutopilotSensorState& State) override;
	virtual bool IsConnected() const override { return bConnected; }
	virtual FName GetBindingName() const override { return TEXT("ArduPilotJSON"); }

	// UObject
	virtual void BeginDestroy() override;

	/**
	 * Parse one servo packet. Returns false if the size / magic is wrong.
	 * Static and socket-free so it can be unit-tested.
	 */
	static bool ParseServoPacket(const uint8* Data, int32 NumBytes, uint16& OutFrameRate, uint32& OutFrameCount,
		TArray<uint16>& OutPwm);

	/** Build the newline-framed JSON reply. Static so it can be unit-tested. */
	static FString BuildStateJson(const FCDSimAutopilotSensorState& State);

	/** PWM microseconds -> normalised [0, 1]. */
	static float PwmToNormalised(uint16 Pwm);

private:
	int32 ListenPort = DefaultPort;
	FSocket* Socket = nullptr;
	TSharedPtr<FInternetAddr> AutopilotAddress;
	uint32 LastFrameCount = 0;
	bool bConnected = false;
	bool bHaveFrame = false;
};

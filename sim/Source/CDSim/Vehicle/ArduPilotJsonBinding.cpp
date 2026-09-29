// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Vehicle/ArduPilotJsonBinding.h"

#include "CDSim.h"
#include "Common/UdpSocketBuilder.h"
#include "IPAddress.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "Interfaces/IPv4/IPv4Endpoint.h"
#include "SocketSubsystem.h"
#include "Sockets.h"

namespace
{
	constexpr int32 HeaderBytes = 2 + 2 + 4; // magic, frame_rate, frame_count
	constexpr int32 MaxPacketBytes = HeaderBytes + 32 * 2;

	uint16 ReadU16(const uint8* Data)
	{
		// Little-endian on the wire, independent of host byte order.
		return static_cast<uint16>(Data[0] | (Data[1] << 8));
	}

	uint32 ReadU32(const uint8* Data)
	{
		return static_cast<uint32>(Data[0]) | (static_cast<uint32>(Data[1]) << 8) | (static_cast<uint32>(Data[2]) << 16)
			| (static_cast<uint32>(Data[3]) << 24);
	}
} // namespace

bool UArduPilotJsonBinding::StartBinding()
{
	StopBinding();

	const FIPv4Endpoint Endpoint(FIPv4Address::Any, static_cast<uint16>(ListenPort));
	Socket = FUdpSocketBuilder(TEXT("CDSimArduPilotJSON"))
				 .AsNonBlocking()
				 .AsReusable()
				 .BoundToEndpoint(Endpoint)
				 .WithReceiveBufferSize(64 * 1024)
				 .WithSendBufferSize(64 * 1024)
				 .Build();
	if (Socket == nullptr)
	{
		UE_LOG(LogCDSim, Error, TEXT("ArduPilot JSON: cannot bind UDP port %d."), ListenPort);
		return false;
	}
	ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
	AutopilotAddress = SocketSubsystem->CreateInternetAddr();
	bConnected = false;
	bHaveFrame = false;
	UE_LOG(LogCDSim, Log, TEXT("ArduPilot JSON: listening on UDP %d (start SITL with --model JSON)."), ListenPort);
	return true;
}

void UArduPilotJsonBinding::StopBinding()
{
	if (Socket != nullptr)
	{
		Socket->Close();
		ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(Socket);
		Socket = nullptr;
	}
	bConnected = false;
}

void UArduPilotJsonBinding::BeginDestroy()
{
	StopBinding();
	Super::BeginDestroy();
}

float UArduPilotJsonBinding::PwmToNormalised(uint16 Pwm)
{
	return FMath::Clamp(static_cast<float>(Pwm - PwmMin) / static_cast<float>(PwmMax - PwmMin), 0.0f, 1.0f);
}

bool UArduPilotJsonBinding::ParseServoPacket(
	const uint8* Data, int32 NumBytes, uint16& OutFrameRate, uint32& OutFrameCount, TArray<uint16>& OutPwm)
{
	if (Data == nullptr || NumBytes < HeaderBytes)
	{
		return false;
	}
	const uint16 Magic = ReadU16(Data);
	int32 Channels = 0;
	if (Magic == Magic16)
	{
		Channels = 16;
	}
	else if (Magic == Magic32)
	{
		Channels = 32;
	}
	else
	{
		return false;
	}
	if (NumBytes != HeaderBytes + Channels * 2)
	{
		return false;
	}
	OutFrameRate = ReadU16(Data + 2);
	OutFrameCount = ReadU32(Data + 4);
	OutPwm.SetNumUninitialized(Channels);
	for (int32 Channel = 0; Channel < Channels; ++Channel)
	{
		OutPwm[Channel] = ReadU16(Data + HeaderBytes + Channel * 2);
	}
	return true;
}

bool UArduPilotJsonBinding::ReceiveActuatorCommands(TArray<float>& OutNormalised)
{
	if (Socket == nullptr)
	{
		return false;
	}

	// Drain the socket and keep only the newest valid frame.
	uint8 Buffer[MaxPacketBytes + 16];
	TArray<uint16> Pwm;
	TArray<uint16> LatestPwm;
	uint32 PendingBytes = 0;
	ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
	TSharedRef<FInternetAddr> Sender = SocketSubsystem->CreateInternetAddr();

	while (Socket->HasPendingData(PendingBytes))
	{
		int32 BytesRead = 0;
		if (!Socket->RecvFrom(Buffer, static_cast<int32>(sizeof(Buffer)), BytesRead, *Sender))
		{
			break;
		}
		uint16 FrameRate = 0;
		uint32 FrameCount = 0;
		if (!ParseServoPacket(Buffer, BytesRead, FrameRate, FrameCount, Pwm))
		{
			UE_LOG(LogCDSim, Verbose, TEXT("ArduPilot JSON: ignored %d-byte packet (bad size/magic)."), BytesRead);
			continue;
		}
		if (bHaveFrame && FrameCount < LastFrameCount)
		{
			UE_LOG(LogCDSim, Log, TEXT("ArduPilot JSON: frame count went backwards (%u -> %u); SITL restarted."),
				LastFrameCount, FrameCount);
		}
		LastFrameCount = FrameCount;
		bHaveFrame = true;
		LatestPwm = Pwm;
		AutopilotAddress = Sender->Clone();
		if (!bConnected)
		{
			bConnected = true;
			UE_LOG(LogCDSim, Log, TEXT("ArduPilot JSON: SITL connected from %s (%u Hz, %d channels)."),
				*Sender->ToString(true), FrameRate, Pwm.Num());
		}
	}

	if (LatestPwm.Num() == 0)
	{
		return false;
	}
	OutNormalised.SetNumZeroed(LatestPwm.Num());
	for (int32 Channel = 0; Channel < LatestPwm.Num(); ++Channel)
	{
		OutNormalised[Channel] = PwmToNormalised(LatestPwm[Channel]);
	}
	return true;
}

FString UArduPilotJsonBinding::BuildStateJson(const FCDSimAutopilotSensorState& S)
{
	// Printf rather than FJsonObject: fixed field order, fixed precision, and
	// no allocation churn at 400 Hz. Framing: leading and trailing "\n".
	return FString::Printf(TEXT("\n{\"timestamp\":%.6f,"
								"\"imu\":{\"gyro\":[%.9f,%.9f,%.9f],\"accel_body\":[%.9f,%.9f,%.9f]},"
								"\"position\":[%.6f,%.6f,%.6f],"
								"\"attitude\":[%.9f,%.9f,%.9f],"
								"\"velocity\":[%.6f,%.6f,%.6f]}\n"),
		S.TimestampS, S.GyroFrdRadps.X, S.GyroFrdRadps.Y, S.GyroFrdRadps.Z, S.AccelFrdMps2.X, S.AccelFrdMps2.Y,
		S.AccelFrdMps2.Z, S.PositionNedM.X, S.PositionNedM.Y, S.PositionNedM.Z, S.AttitudeRpyRad.X,
		S.AttitudeRpyRad.Y, S.AttitudeRpyRad.Z, S.VelocityNedMps.X, S.VelocityNedMps.Y, S.VelocityNedMps.Z);
}

void UArduPilotJsonBinding::SendSensorState(const FCDSimAutopilotSensorState& State)
{
	if (Socket == nullptr || !bConnected || !AutopilotAddress.IsValid())
	{
		return; // Nobody to reply to yet: SITL always speaks first.
	}
	const FString Json = BuildStateJson(State);
	const FTCHARToUTF8 Utf8(*Json);
	int32 BytesSent = 0;
	if (!Socket->SendTo(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length(), BytesSent, *AutopilotAddress))
	{
		UE_LOG(LogCDSim, Verbose, TEXT("ArduPilot JSON: send failed."));
	}
}

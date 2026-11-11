// Adaptador Health Connect (Android). Roda no device via Capacitor.
// Plugin sugerido: @kiwi-health/capacitor-health-connect (confirmar nomes exatos de tipos/métodos na doc).
// import { HealthConnect } from "@kiwi-health/capacitor-health-connect";
import type { DataSource, Activity, DailyWellness } from "@copiloto/shared";
import { CAP_HEALTH_CONNECT } from "@copiloto/shared";
import { activitiesFromHC, wellnessFromHC } from "./healthConnectMap";

const READ_TYPES = ["ExerciseSession", "HeartRateSeries", "SleepSession", "OxygenSaturation", "Steps"];

export class HealthConnectDataSource implements DataSource {
  readonly name = "garmin-via-health-connect";
  readonly capabilities = CAP_HEALTH_CONNECT; // { hrv:false, sleepScore:false, ... }

  async ensurePermissions(): Promise<void> {
    // TODO: await HealthConnect.requestHealthPermissions({ read: READ_TYPES });
    // TODO: verificar disponibilidade do Health Connect no device (getSdkStatus).
  }

  async getActivities(from: string, to: string): Promise<Activity[]> {
    await this.ensurePermissions();
    const filter = { startTime: `${from}T00:00:00.000Z`, endTime: `${to}T23:59:59.999Z` };
    // TODO: const ex = await HealthConnect.readRecords({ type: "ExerciseSession", timeRangeFilter: filter });
    // TODO: const hr = await HealthConnect.readRecords({ type: "HeartRateSeries", timeRangeFilter: filter });
    // const hrSamples = (hr.records||[]).flatMap(r => r.samples);
    // return activitiesFromHC(ex.records || [], hrSamples);
    return activitiesFromHC([], []); // stub
  }

  async getWellness(date: string): Promise<DailyWellness | null> {
    await this.ensurePermissions();
    const filter = { startTime: `${date}T00:00:00.000Z`, endTime: `${date}T23:59:59.999Z` };
    // TODO: const sl = await HealthConnect.readRecords({ type: "SleepSession", timeRangeFilter: filter });
    // return wellnessFromHC(date, (sl.records||[])[0]);
    return wellnessFromHC(date, undefined); // stub
  }
}

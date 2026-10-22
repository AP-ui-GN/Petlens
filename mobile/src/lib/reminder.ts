/**
 * A local weekly reminder. Permission is requested only when the owner turns
 * this on. Nothing is sent to a server.
 */

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

const REMINDER_ID = 'silverpaws-weekly-walk-check';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export async function disableWalkReminder(): Promise<void> {
  await Notifications.cancelScheduledNotificationAsync(REMINDER_ID).catch(() => undefined);
}

export async function enableWalkReminder(): Promise<{ ok: true } | { ok: false; message: string }> {
  const existing = await Notifications.getPermissionsAsync();
  let granted = existing.granted;
  if (!granted) {
    const asked = await Notifications.requestPermissionsAsync();
    granted = asked.granted;
  }
  if (!granted) {
    return { ok: false, message: 'Notifications are off for PetLens. You can allow them in the phone settings.' };
  }

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('walk-check', {
      name: 'Walk check',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }

  await disableWalkReminder();
  await Notifications.scheduleNotificationAsync({
    identifier: REMINDER_ID,
    content: {
      title: 'Time for a walk check',
      body: 'A short side-on clip is enough for another wellness note. This is not a medical reminder.',
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.WEEKLY,
      weekday: 1,
      hour: 10,
      minute: 0,
      channelId: Platform.OS === 'android' ? 'walk-check' : undefined,
    },
  });
  return { ok: true };
}

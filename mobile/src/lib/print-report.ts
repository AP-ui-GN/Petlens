/**
 * Turn report HTML into a PDF and hand it to the system share sheet.
 */

import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';

export async function sharePdf(html: string, dialogTitle: string): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    // Create a local PDF first, then pass it to the platform share sheet.
    const file = await Print.printToFileAsync({ html });
    const available = await Sharing.isAvailableAsync();
    if (!available) {
      return { ok: false, message: 'Sharing is not available on this device.' };
    }
    await Sharing.shareAsync(file.uri, {
      mimeType: 'application/pdf',
      dialogTitle,
      UTI: 'com.adobe.pdf',
    });
    return { ok: true };
  } catch {
    return { ok: false, message: 'The PDF could not be created. Please try again.' };
  }
}

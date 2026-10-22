/**
 * Minimal multipart/form-data reader for the single-file upload on /api/analyze.
 *
 * The route needs one video part plus a few short text fields, so a buffer-based
 * reader is enough and keeps the server dependency-free. The request size is
 * capped by express.raw() before this code runs.
 */

// Guards against a request with thousands of tiny parts.
const MAX_PARTS = 20;

// Text fields in this API are names and numbers, never documents.
const MAX_FIELD_LENGTH = 4096;

const CRLF = "\r\n";
const HEADER_SEPARATOR = "\r\n\r\n";

export interface MultipartFile {
  fieldName: string;
  fileName: string;
  contentType: string;
  data: Buffer;
}

export interface MultipartForm {
  fields: Record<string, string>;
  files: MultipartFile[];
}

export class MultipartError extends Error {}

/** Read the boundary token out of a Content-Type header. */
export function parseBoundary(contentType: string | undefined): string | null {
  if (!contentType || !contentType.toLowerCase().includes("multipart/form-data")) {
    return null;
  }

  const match = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(contentType);
  const boundary = (match?.[1] ?? match?.[2])?.trim();
  return boundary ? boundary : null;
}

function parseHeaders(rawHeaders: string): Map<string, string> {
  const headers = new Map<string, string>();

  for (const line of rawHeaders.split(CRLF)) {
    const separator = line.indexOf(":");
    if (separator === -1) continue;
    headers.set(
      line.slice(0, separator).trim().toLowerCase(),
      line.slice(separator + 1).trim(),
    );
  }

  return headers;
}

/**
 * Read a parameter out of a header value, e.g. `name` from
 * `form-data; name="video"; filename="walk.mp4"`.
 */
function readParameter(headerValue: string, parameter: string): string {
  const pattern = new RegExp(`${parameter}=(?:"([^"]*)"|([^;]*))`, "i");
  const match = pattern.exec(headerValue);
  return (match?.[1] ?? match?.[2] ?? "").trim();
}


/**
 * Find a MIME boundary only when it occupies a boundary line. The token can
 * legitimately occur as arbitrary bytes inside a video, so a raw indexOf hit
 * is not enough to separate parts.
 */
function findBoundaryLine(body: Buffer, delimiter: Buffer, start: number): number {
  let candidate = body.indexOf(delimiter, start);
  while (candidate !== -1) {
    const atLineStart =
      candidate === 0 ||
      (candidate >= 2 &&
        body[candidate - 2] === 0x0d &&
        body[candidate - 1] === 0x0a);
    const suffixAt = candidate + delimiter.length;
    const hasValidSuffix =
      (body[suffixAt] === 0x0d && body[suffixAt + 1] === 0x0a) ||
      (body[suffixAt] === 0x2d && body[suffixAt + 1] === 0x2d);
    if (atLineStart && hasValidSuffix) return candidate;
    candidate = body.indexOf(delimiter, candidate + 1);
  }
  return -1;
}

/**
 * Split a multipart body into its fields and files.
 *
 * @throws MultipartError when the body does not follow the boundary structure.
 */
export function parseMultipart(body: Buffer, boundary: string): MultipartForm {
  const delimiter = Buffer.from(`--${boundary}`);
  const fields: Record<string, string> = {};
  const files: MultipartFile[] = [];

  let cursor = findBoundaryLine(body, delimiter, 0);
  if (cursor === -1) {
    throw new MultipartError("The upload did not contain a multipart boundary.");
  }

  let partCount = 0;

  while (cursor !== -1) {
    let partStart = cursor + delimiter.length;

    // The final delimiter is followed by "--".
    if (body.slice(partStart, partStart + 2).toString() === "--") break;

    if (body.slice(partStart, partStart + 2).toString() === CRLF) {
      partStart += 2;
    }

    const nextDelimiter = findBoundaryLine(body, delimiter, partStart);
    if (nextDelimiter === -1) {
      throw new MultipartError("The upload ended before its closing boundary.");
    }

    partCount += 1;
    if (partCount > MAX_PARTS) {
      throw new MultipartError("The upload contained too many parts.");
    }

    // Everything up to the CRLF that precedes the next delimiter is the part.
    const partEnd = nextDelimiter - CRLF.length;
    const part = body.slice(partStart, Math.max(partStart, partEnd));

    const headerEnd = part.indexOf(HEADER_SEPARATOR);
    if (headerEnd !== -1) {
      const headers = parseHeaders(part.slice(0, headerEnd).toString("utf8"));
      const disposition = headers.get("content-disposition") ?? "";
      const fieldName = readParameter(disposition, "name");
      const content = part.slice(headerEnd + HEADER_SEPARATOR.length);

      if (fieldName && disposition.toLowerCase().startsWith("form-data")) {
        const fileName = readParameter(disposition, "filename");
        if (fileName) {
          files.push({
            fieldName,
            fileName,
            contentType: headers.get("content-type") ?? "",
            data: content,
          });
        } else if (content.length <= MAX_FIELD_LENGTH) {
          fields[fieldName] = content.toString("utf8");
        }
      }
    }

    cursor = nextDelimiter;
  }

  return { fields, files };
}

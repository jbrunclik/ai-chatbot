/**
 * Script to generate valid PNG test images
 * Run with: node web/tests/fixtures/generate-test-images.cjs
 */

const fs = require('fs');
const zlib = require('zlib');
const path = require('path');

function writeUInt32BE(value) {
  const buf = Buffer.allocUnsafe(4);
  buf.writeUInt32BE(value, 0);
  return buf;
}

function crc32(data) {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    crc ^= data[i];
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function createChunk(type, data) {
  const typeBuf = Buffer.from(type, 'ascii');
  const length = writeUInt32BE(data.length);
  const chunkData = Buffer.concat([typeBuf, data]);
  const crc = writeUInt32BE(crc32(chunkData));
  return Buffer.concat([length, chunkData, crc]);
}

function generatePngBuffer(width, height, r, g, b) {
  // PNG file signature
  const pngSignature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

  // IHDR chunk
  const ihdrData = Buffer.allocUnsafe(13);
  writeUInt32BE(width).copy(ihdrData, 0);
  writeUInt32BE(height).copy(ihdrData, 4);
  ihdrData[8] = 8; // bit depth
  ihdrData[9] = 2; // color type (RGB)
  ihdrData[10] = 0; // compression
  ihdrData[11] = 0; // filter
  ihdrData[12] = 0; // interlace
  const ihdrChunk = createChunk('IHDR', ihdrData);

  // Generate image data: each row has a filter byte (0 = none) + RGB pixels
  const bytesPerRow = width * 3;
  const rowSize = 1 + bytesPerRow; // filter byte + pixel data
  const imageData = Buffer.allocUnsafe(rowSize * height);

  // Fill with solid color
  for (let y = 0; y < height; y++) {
    const rowStart = y * rowSize;
    imageData[rowStart] = 0; // filter type: none
    for (let x = 0; x < width; x++) {
      const pixelOffset = rowStart + 1 + x * 3;
      imageData[pixelOffset] = r;
      imageData[pixelOffset + 1] = g;
      imageData[pixelOffset + 2] = b;
    }
  }

  // Compress image data using zlib
  const compressedData = zlib.deflateSync(imageData);
  const idatChunk = createChunk('IDAT', compressedData);
  const iendChunk = createChunk('IEND', Buffer.alloc(0));

  return Buffer.concat([pngSignature, ihdrChunk, idatChunk, iendChunk]);
}

// Generate test images
const fixturesDir = path.join(__dirname);
const images = {
  'red-400x400.png': generatePngBuffer(400, 400, 255, 0, 0),
  'blue-400x400.png': generatePngBuffer(400, 400, 0, 0, 255),
  'green-400x400.png': generatePngBuffer(400, 400, 0, 255, 0),
};

// Write images to files
for (const [filename, buffer] of Object.entries(images)) {
  const filepath = path.join(fixturesDir, filename);
  fs.writeFileSync(filepath, buffer);
  console.log(`Generated ${filename} (${buffer.length} bytes)`);
}

console.log('\nTest images generated successfully!');


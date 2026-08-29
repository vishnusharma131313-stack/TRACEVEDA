#include <LittleFS.h>

// ======================================================
// TRACEVEDA — LITTLEFS CLEAR / RESET TOOL
//
// Purpose:
// Clear all Traceveda offline-buffer files before testing.
//
// Upload this SAME sketch to:
//   1. Truck Node ESP32
//   2. Storage Node ESP32
//
// After successful clearing:
//   Upload the respective final Truck/Storage firmware.
//
// ======================================================

const char* TRUCK_BUFFER_FILE = "/truck_iot_buffer.txt";
const char* TRUCK_REMAINING_FILE = "/truck_iot_remaining.txt";

const char* STORAGE_BUFFER_FILE = "/iot_buffer.txt";
const char* STORAGE_REMAINING_FILE = "/iot_remaining.txt";


void setup()
{
  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("========================================");
  Serial.println(" TRACEVEDA LITTLEFS CLEAR TOOL");
  Serial.println("========================================");

  // ----------------------------------------------------
  // Initialize LittleFS
  // ----------------------------------------------------

  if (!LittleFS.begin(true))
  {
    Serial.println("ERROR: LittleFS initialization FAILED!");
    Serial.println("Nothing was cleared.");
    Serial.println("========================================");

    while (true)
    {
      delay(1000);
    }
  }

  Serial.println("LittleFS initialized successfully.");
  Serial.println();


  // ----------------------------------------------------
  // Show existing files
  // ----------------------------------------------------

  Serial.println("Checking Traceveda buffer files...");

  bool truckBufferExists =
    LittleFS.exists(TRUCK_BUFFER_FILE);

  bool truckRemainingExists =
    LittleFS.exists(TRUCK_REMAINING_FILE);

  bool storageBufferExists =
    LittleFS.exists(STORAGE_BUFFER_FILE);

  bool storageRemainingExists =
    LittleFS.exists(STORAGE_REMAINING_FILE);


  Serial.println();

  Serial.print("Truck buffer: ");
  Serial.println(
    truckBufferExists ? "FOUND" : "NOT FOUND"
  );

  Serial.print("Truck remaining: ");
  Serial.println(
    truckRemainingExists ? "FOUND" : "NOT FOUND"
  );

  Serial.print("Storage buffer: ");
  Serial.println(
    storageBufferExists ? "FOUND" : "NOT FOUND"
  );

  Serial.print("Storage remaining: ");
  Serial.println(
    storageRemainingExists ? "FOUND" : "NOT FOUND"
  );

  Serial.println();


  // ----------------------------------------------------
  // Remove Truck files
  // ----------------------------------------------------

  Serial.println("Clearing Truck Node buffers...");

  if (LittleFS.exists(TRUCK_BUFFER_FILE))
  {
    if (LittleFS.remove(TRUCK_BUFFER_FILE))
    {
      Serial.println("Truck buffer cleared.");
    }
    else
    {
      Serial.println("ERROR: Could not remove Truck buffer.");
    }
  }
  else
  {
    Serial.println("Truck buffer already empty.");
  }


  if (LittleFS.exists(TRUCK_REMAINING_FILE))
  {
    if (LittleFS.remove(TRUCK_REMAINING_FILE))
    {
      Serial.println("Truck remaining buffer cleared.");
    }
    else
    {
      Serial.println(
        "ERROR: Could not remove Truck remaining buffer."
      );
    }
  }
  else
  {
    Serial.println("Truck remaining buffer already empty.");
  }


  // ----------------------------------------------------
  // Remove Storage files
  // ----------------------------------------------------

  Serial.println();
  Serial.println("Clearing Storage Node buffers...");

  if (LittleFS.exists(STORAGE_BUFFER_FILE))
  {
    if (LittleFS.remove(STORAGE_BUFFER_FILE))
    {
      Serial.println("Storage buffer cleared.");
    }
    else
    {
      Serial.println(
        "ERROR: Could not remove Storage buffer."
      );
    }
  }
  else
  {
    Serial.println("Storage buffer already empty.");
  }


  if (LittleFS.exists(STORAGE_REMAINING_FILE))
  {
    if (LittleFS.remove(STORAGE_REMAINING_FILE))
    {
      Serial.println("Storage remaining buffer cleared.");
    }
    else
    {
      Serial.println(
        "ERROR: Could not remove Storage remaining buffer."
      );
    }
  }
  else
  {
    Serial.println(
      "Storage remaining buffer already empty."
    );
  }


  // ----------------------------------------------------
  // Verify
  // ----------------------------------------------------

  Serial.println();
  Serial.println("========================================");
  Serial.println("             VERIFICATION");
  Serial.println("========================================");

  bool anyBufferLeft = false;


  if (LittleFS.exists(TRUCK_BUFFER_FILE))
  {
    Serial.println("WARNING: Truck buffer still exists.");
    anyBufferLeft = true;
  }

  if (LittleFS.exists(TRUCK_REMAINING_FILE))
  {
    Serial.println(
      "WARNING: Truck remaining buffer still exists."
    );
    anyBufferLeft = true;
  }

  if (LittleFS.exists(STORAGE_BUFFER_FILE))
  {
    Serial.println("WARNING: Storage buffer still exists.");
    anyBufferLeft = true;
  }

  if (LittleFS.exists(STORAGE_REMAINING_FILE))
  {
    Serial.println(
      "WARNING: Storage remaining buffer still exists."
    );
    anyBufferLeft = true;
  }


  if (!anyBufferLeft)
  {
    Serial.println();
    Serial.println("SUCCESS!");
    Serial.println(
      "All Traceveda LittleFS buffer files are EMPTY."
    );
  }
  else
  {
    Serial.println();
    Serial.println(
      "WARNING: One or more buffer files remain."
    );
  }


  Serial.println();
  Serial.println("========================================");
  Serial.println(" CLEAR OPERATION COMPLETE");
  Serial.println("========================================");
  Serial.println();
  Serial.println(
    "You can now upload the respective"
  );
  Serial.println(
    "Truck Node / Storage Node firmware."
  );

  // Stop here.
  while (true)
  {
    delay(1000);
  }
}


void loop()
{
  // Nothing to do.
}
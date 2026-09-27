# Project Proposal: Smart Clinic

**1. Project Name and Description**
Smart Clinic - A centralized clinic management system designed to streamline appointment scheduling and manage comprehensive medical histories in one unified platform.

**2. Business Need / Problem Solved**
Many clinics rely on manual and scattered administrative processes, which often lead to human errors, double-booked appointments, and fragmented medical records. This system provides a structured solution to organize data, prevent conflicts, and save valuable time for the medical staff.

**3. Key Users and Their Roles**
* **Secretary / Receptionist:** Responsible for scheduling and canceling appointments, as well as managing patients' personal details.
* **Doctor:** Responsible for writing visit summaries, reviewing medical histories, and updating patients' personal medical files.
* **Clinic Manager:** Monitors doctors' schedules, analyzes peak hours, and tracks patient arrival rates.

**4. Main Business Process**
A patient requests an appointment -> The secretary checks availability, schedules the appointment, and sends a reminder -> On the day of the appointment, the doctor reviews the patient's medical file beforehand -> The examination takes place, and a visit summary is recorded -> If needed, a follow-up appointment is scheduled, and the system updates the visit status accordingly.

**5. Information Flow**
* **Inputs:** Appointment requests, patient personal details (e.g., ID, Name), and doctors' availability.
* **Creators/Updaters:** Secretaries create and update appointments; Doctors create and update medical records (visit summaries).
* **Outputs:** Weekly schedule reports, visit histories, and statistical reports on resource utilization and peak hours.

**6. Expected Business Value**
Centralizing administrative processes reduces dependency on manual labor, prevents scheduling conflicts (double-booking), unifies medical records, improves overall patient service, and supports data-driven decision-making (such as shift planning based on peak hour analysis).

**7. Main Entities and Relationships**
* **Entities:** Doctor, Patient, Appointment, Visit (Medical Summary).
* **Relationships:** 
  * A `Patient` can have multiple `Appointments` and `Visits` (1-to-Many).
  * A `Doctor` handles multiple `Appointments` (1-to-Many).
  * An `Appointment` is linked to exactly one `Doctor` and one `Patient`.
  * A `Visit` is generated from a completed `Appointment` to store the medical summary.

**8. Main Use Cases**
* **Conflict-Free Scheduling:** The system schedules a new appointment while automatically detecting and preventing time-slot overlaps.
* **Medical History Review:** A doctor accesses a patient's historical records right before an examination to gain insights and provide better, informed medical care.

**9. Future Extension Idea**
Integration of an automated reminder system (e.g., via an external SMS or EMAIL API) to automatically notify patients one day prior to their scheduled appointment.

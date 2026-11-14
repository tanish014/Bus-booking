/**
 * BusGo - Frontend Application Logic
 * Interacts with Bus Booking REST API endpoints:
 *   GET  /health, GET /ready
 *   GET  /routes, GET /trips?route_id=...&date=...
 *   GET  /trips/<id>/seats
 *   POST /bookings
 *   GET  /bookings/<pnr>
 *   POST /bookings/<pnr>/cancel
 */

document.addEventListener("DOMContentLoaded", () => {
  // Global State
  const state = {
    routes: [],
    selectedRoute: null,
    selectedTrip: null,
    selectedSeat: null,
    trips: [],
  };

  // DOM Elements
  const alertBox = document.getElementById("alert-box");
  const systemStatus = document.getElementById("system-status");
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const appVersionBadge = document.getElementById("app-version-badge");

  // Tabs
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  // Booking Flow Elements
  const searchForm = document.getElementById("search-form");
  const routeSelect = document.getElementById("route-select");
  const travelDateInput = document.getElementById("travel-date");
  const tripsSection = document.getElementById("trips-section");
  const tripsList = document.getElementById("trips-list");
  const tripsSummary = document.getElementById("trips-summary");

  const bookingSection = document.getElementById("booking-section");
  const selectedTripInfo = document.getElementById("selected-trip-info");
  const seatLayout = document.getElementById("seat-layout");
  const selectedSeatDisplay = document.getElementById("selected-seat-display");
  const selectedFareTag = document.getElementById("selected-fare-tag");

  const bookingForm = document.getElementById("booking-form");
  const passengerName = document.getElementById("passenger-name");
  const passengerAge = document.getElementById("passenger-age");
  const passengerPhone = document.getElementById("passenger-phone");
  const boardingStop = document.getElementById("boarding-stop");
  const dropStop = document.getElementById("drop-stop");
  const confirmBookingBtn = document.getElementById("confirm-booking-btn");

  const confirmationCard = document.getElementById("confirmation-card");
  const ticketDetailsBox = document.getElementById("ticket-details-box");
  const bookAnotherBtn = document.getElementById("book-another-btn");

  // Manage / PNR Elements
  const pnrForm = document.getElementById("pnr-form");
  const pnrInput = document.getElementById("pnr-input");
  const pnrResult = document.getElementById("pnr-result");

  // ----------------------------------------------------------------------
  // Utilities: Alerts & Notification
  // ----------------------------------------------------------------------
  function showAlert(message, type = "error") {
    alertBox.className = `alert alert-${type}`;
    alertBox.textContent = message;
    alertBox.classList.remove("hidden");
    alertBox.scrollIntoView({ behavior: "smooth", block: "center" });

    // Auto-dismiss after 6 seconds for info/success
    if (type !== "error") {
      setTimeout(() => {
        alertBox.classList.add("hidden");
      }, 6000);
    }
  }

  function hideAlert() {
    alertBox.classList.add("hidden");
  }

  // ----------------------------------------------------------------------
  // Tab Switching
  // ----------------------------------------------------------------------
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabButtons.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");
      hideAlert();
    });
  });

  // ----------------------------------------------------------------------
  // System Health Monitor
  // ----------------------------------------------------------------------
  async function checkSystemHealth() {
    try {
      const [healthRes, readyRes] = await Promise.all([
        fetch("/health"),
        fetch("/ready"),
      ]);

      if (healthRes.ok && readyRes.ok) {
        const healthData = await healthRes.json();
        const readyData = await readyRes.json();
        statusDot.className = "status-indicator online";
        statusText.textContent = `Online (${readyData.database})`;
        appVersionBadge.textContent = `Version: ${healthData.version || "dev"}`;
      } else {
        statusDot.className = "status-indicator offline";
        statusText.textContent = "Service Degraded";
      }
    } catch (err) {
      statusDot.className = "status-indicator offline";
      statusText.textContent = "Offline";
    }
  }

  // ----------------------------------------------------------------------
  // Initial Setup: Default Date & Fetch Routes
  // ----------------------------------------------------------------------
  function setupDatePicker() {
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const minDateStr = today.toISOString().split("T")[0];
    const defaultDateStr = tomorrow.toISOString().split("T")[0];

    travelDateInput.min = minDateStr;
    travelDateInput.value = defaultDateStr;
  }

  async function loadRoutes() {
    try {
      const res = await fetch("/routes");
      if (!res.ok) throw new Error("Failed to load routes from backend");
      const data = await res.json();
      state.routes = data;

      routeSelect.innerHTML = '<option value="" disabled selected>-- Select a route --</option>';
      data.forEach((r) => {
        const opt = document.createElement("option");
        opt.value = r.id;
        opt.textContent = `${r.origin} ➔ ${r.destination} (${r.stops.length} stops)`;
        routeSelect.appendChild(opt);
      });
    } catch (err) {
      showAlert(err.message, "error");
    }
  }

  // ----------------------------------------------------------------------
  // Step 1: Search Trips
  // ----------------------------------------------------------------------
  searchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();

    const routeId = routeSelect.value;
    const dateVal = travelDateInput.value;

    if (!routeId || !dateVal) {
      showAlert("Please choose both a route and a travel date.");
      return;
    }

    state.selectedRoute = state.routes.find((r) => r.id === parseInt(routeId, 10));
    state.selectedTrip = null;
    state.selectedSeat = null;

    // Reset downstream sections
    tripsSection.classList.add("hidden");
    bookingSection.classList.add("hidden");
    confirmationCard.classList.add("hidden");

    try {
      const res = await fetch(`/trips?route_id=${routeId}&date=${dateVal}`);
      if (!res.ok) throw new Error("Failed to fetch trips");
      const trips = await res.json();
      state.trips = trips;

      renderTrips(trips);
    } catch (err) {
      showAlert(`Error fetching trips: ${err.message}`, "error");
    }
  });

  // ----------------------------------------------------------------------
  // Step 2: Render Trips
  // ----------------------------------------------------------------------
  function renderTrips(trips) {
    tripsList.innerHTML = "";
    if (trips.length === 0) {
      tripsSummary.textContent = "No trips scheduled for this date and route.";
      tripsSection.classList.remove("hidden");
      return;
    }

    tripsSummary.textContent = `Found ${trips.length} scheduled departures for ${travelDateInput.value}`;

    trips.forEach((trip) => {
      const card = document.createElement("div");
      card.className = "trip-card";
      card.innerHTML = `
        <div class="trip-card-header">
          <div>
            <div class="trip-time">${trip.departure_time}</div>
            <div class="text-muted">${state.selectedRoute.origin} ➔ ${state.selectedRoute.destination}</div>
          </div>
          <div class="trip-fare">₹${trip.fare}</div>
        </div>
        <div class="trip-meta">
          <span>📅 Date: <strong>${trip.travel_date}</strong></span>
          <span>🪑 Total Capacity: <strong>${trip.total_seats} seats</strong></span>
        </div>
        <button class="btn btn-outline select-trip-btn" data-trip-id="${trip.id}">
          Select & View Seats
        </button>
      `;

      const selectBtn = card.querySelector(".select-trip-btn");
      selectBtn.addEventListener("click", () => {
        document.querySelectorAll(".trip-card").forEach((c) => c.classList.remove("active"));
        card.classList.add("active");
        handleSelectTrip(trip);
      });

      tripsList.appendChild(card);
    });

    tripsSection.classList.remove("hidden");
    tripsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ----------------------------------------------------------------------
  // Step 3: Load Seat Map & Stops
  // ----------------------------------------------------------------------
  async function handleSelectTrip(trip) {
    state.selectedTrip = trip;
    state.selectedSeat = null;
    hideAlert();
    updateSeatSelectionUI();

    selectedTripInfo.textContent = `${state.selectedRoute.origin} to ${state.selectedRoute.destination} | Departure: ${trip.departure_time} | Fare: ₹${trip.fare}`;

    // Populate Boarding and Drop Stops
    populateStopsDropdown(state.selectedRoute.stops);

    try {
      const res = await fetch(`/trips/${trip.id}/seats`);
      if (!res.ok) throw new Error("Failed to load seats for trip");
      const seatData = await res.json();

      renderSeatMap(seatData.seats);
      bookingSection.classList.remove("hidden");
      bookingSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showAlert(`Error loading seat map: ${err.message}`, "error");
    }
  }

  function populateStopsDropdown(stops) {
    boardingStop.innerHTML = "";
    dropStop.innerHTML = "";

    stops.forEach((stop, index) => {
      // Boarding: can be any stop except the last one
      if (index < stops.length - 1) {
        const opt = document.createElement("option");
        opt.value = stop;
        opt.textContent = stop;
        boardingStop.appendChild(opt);
      }
      // Drop: can be any stop except the first one
      if (index > 0) {
        const opt = document.createElement("option");
        opt.value = stop;
        opt.textContent = stop;
        dropStop.appendChild(opt);
      }
    });

    // Default: origin and destination
    if (boardingStop.options.length > 0) boardingStop.selectedIndex = 0;
    if (dropStop.options.length > 0) dropStop.selectedIndex = dropStop.options.length - 1;
  }

  function renderSeatMap(seats) {
    seatLayout.innerHTML = "";

    // 40 seats arranged in 10 rows × (2 seats + aisle + 2 seats)
    const totalRows = 10;
    const seatMap = new Map();
    seats.forEach((s) => seatMap.set(s.seat_no, s.status));

    for (let row = 0; row < totalRows; row++) {
      const s1 = row * 4 + 1;
      const s2 = row * 4 + 2;
      const s3 = row * 4 + 3;
      const s4 = row * 4 + 4;

      // Seat 1
      createSeatElement(s1, seatMap.get(s1));
      // Seat 2
      createSeatElement(s2, seatMap.get(s2));
      // Aisle gap
      const aisle = document.createElement("div");
      aisle.className = "seat-aisle";
      seatLayout.appendChild(aisle);
      // Seat 3
      createSeatElement(s3, seatMap.get(s3));
      // Seat 4
      createSeatElement(s4, seatMap.get(s4));
    }
  }

  function createSeatElement(seatNo, status) {
    const seatDiv = document.createElement("div");
    seatDiv.className = `seat-item ${status === "BOOKED" ? "booked" : "available"}`;
    seatDiv.textContent = seatNo;
    seatDiv.dataset.seatNo = seatNo;

    if (status === "BOOKED") {
      seatDiv.title = `Seat ${seatNo}: Already Booked`;
    } else {
      seatDiv.title = `Seat ${seatNo}: Available`;
      seatDiv.addEventListener("click", () => {
        handleSeatClick(seatNo);
      });
    }

    seatLayout.appendChild(seatDiv);
  }

  function handleSeatClick(seatNo) {
    if (state.selectedSeat === seatNo) {
      state.selectedSeat = null; // deselect
    } else {
      state.selectedSeat = seatNo;
    }

    // Update visuals
    document.querySelectorAll(".seat-item").forEach((el) => {
      const num = parseInt(el.dataset.seatNo, 10);
      if (num === state.selectedSeat) {
        el.classList.add("selected");
      } else {
        el.classList.remove("selected");
      }
    });

    updateSeatSelectionUI();
  }

  function updateSeatSelectionUI() {
    if (state.selectedSeat && state.selectedTrip) {
      selectedSeatDisplay.innerHTML = `<span>Selected Seat: <strong>Seat #${state.selectedSeat}</strong></span>
                                       <span class="fare-tag">Fare: ₹${state.selectedTrip.fare}</span>`;
      confirmBookingBtn.disabled = false;
    } else {
      selectedSeatDisplay.innerHTML = `<span>Selected Seat: <strong>None</strong></span>
                                       <span class="fare-tag">Fare: ₹0</span>`;
      confirmBookingBtn.disabled = true;
    }
  }

  // ----------------------------------------------------------------------
  // Step 4: Create Booking
  // ----------------------------------------------------------------------
  bookingForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();

    if (!state.selectedTrip || !state.selectedSeat) {
      showAlert("Please select a seat on the bus layout before confirming.");
      return;
    }

    const bStop = boardingStop.value;
    const dStop = dropStop.value;
    const stopsList = state.selectedRoute.stops;

    if (stopsList.indexOf(bStop) >= stopsList.indexOf(dStop)) {
      showAlert("Boarding stop must come before drop stop on this route.");
      return;
    }

    const payload = {
      trip_id: state.selectedTrip.id,
      seat_no: state.selectedSeat,
      travel_date: state.selectedTrip.travel_date,
      boarding_stop: bStop,
      drop_stop: dStop,
      passenger: {
        name: passengerName.value.trim(),
        age: parseInt(passengerAge.value, 10),
        phone: passengerPhone.value.trim(),
      },
    };

    confirmBookingBtn.disabled = true;
    confirmBookingBtn.textContent = "Processing reservation...";

    try {
      const res = await fetch("/bookings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (res.status === 201) {
        showConfirmation(data, payload);
      } else if (res.status === 409) {
        showAlert("Seat was just booked by another user! Refreshing seat map...", "error");
        // Reload seat map
        handleSelectTrip(state.selectedTrip);
      } else {
        showAlert(data.error || "Failed to create booking", "error");
      }
    } catch (err) {
      showAlert(`Network error: ${err.message}`, "error");
    } finally {
      confirmBookingBtn.disabled = false;
      confirmBookingBtn.textContent = "Confirm & Book Seat";
    }
  });

  function showConfirmation(bookingData, payload) {
    bookingSection.classList.add("hidden");
    tripsSection.classList.add("hidden");

    ticketDetailsBox.innerHTML = `
      <div class="ticket-pnr-row">
        <div>
          <span class="text-muted">PNR NUMBER</span>
          <div class="ticket-pnr-value">${bookingData.pnr}</div>
        </div>
        <div class="status-badge confirmed">${bookingData.status}</div>
      </div>
      <div class="ticket-grid">
        <div><span>Passenger Name</span><strong>${payload.passenger.name}</strong></div>
        <div><span>Age / Phone</span><strong>${payload.passenger.age} yrs / ${payload.passenger.phone}</strong></div>
        <div><span>Route</span><strong>${state.selectedRoute.origin} ➔ ${state.selectedRoute.destination}</strong></div>
        <div><span>Seat Number</span><strong>Seat #${bookingData.seat_no}</strong></div>
        <div><span>Boarding Stop</span><strong>${payload.boarding_stop}</strong></div>
        <div><span>Drop Stop</span><strong>${payload.drop_stop}</strong></div>
        <div><span>Travel Date</span><strong>${payload.travel_date}</strong></div>
        <div><span>Total Fare Paid</span><strong>₹${bookingData.fare}</strong></div>
      </div>
    `;

    confirmationCard.classList.remove("hidden");
    confirmationCard.scrollIntoView({ behavior: "smooth", block: "center" });
    showAlert("Booking confirmed! Please save your PNR number for reference.", "success");
  }

  bookAnotherBtn.addEventListener("click", () => {
    confirmationCard.classList.add("hidden");
    state.selectedTrip = null;
    state.selectedSeat = null;
    bookingForm.reset();
    updateSeatSelectionUI();
    tripsSection.classList.remove("hidden");
    tripsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  // ----------------------------------------------------------------------
  // PNR Status & Cancellation Flow
  // ----------------------------------------------------------------------
  pnrForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();

    const pnr = pnrInput.value.trim().toUpperCase();
    if (!pnr) return;

    try {
      const res = await fetch(`/bookings/${pnr}`);
      const data = await res.json();

      if (!res.ok) {
        pnrResult.classList.add("hidden");
        showAlert(data.error || "PNR record not found", "error");
        return;
      }

      renderPnrDetails(data);
    } catch (err) {
      showAlert(`Error retrieving PNR: ${err.message}`, "error");
    }
  });

  function renderPnrDetails(booking) {
    const isConfirmed = booking.status === "CONFIRMED";
    pnrResult.innerHTML = `
      <div class="pnr-result-box">
        <div class="pnr-header-row">
          <div>
            <span class="text-muted">RESERVATION CODE</span>
            <h3 style="font-family: monospace; font-size: 1.4rem; color: var(--primary);">${booking.pnr}</h3>
          </div>
          <span class="status-badge ${isConfirmed ? "confirmed" : "cancelled"}">${booking.status}</span>
        </div>
        <div class="ticket-grid">
          <div><span>Passenger Name</span><strong>${booking.passenger_name}</strong></div>
          <div><span>Trip Reference</span><strong>Trip #${booking.trip_id}</strong></div>
          <div><span>Seat Number</span><strong>Seat #${booking.seat_no}</strong></div>
          <div><span>Journey Leg</span><strong>${booking.boarding_stop} ➔ ${booking.drop_stop}</strong></div>
          <div><span>Booking Time (UTC)</span><strong>${booking.created_at || "N/A"}</strong></div>
        </div>

        ${
          isConfirmed
            ? `
          <div class="pnr-actions">
            <button id="cancel-ticket-btn" class="btn btn-danger">
              Cancel This Reservation
            </button>
          </div>
        `
            : ""
        }
      </div>
    `;

    pnrResult.classList.remove("hidden");

    if (isConfirmed) {
      const cancelBtn = document.getElementById("cancel-ticket-btn");
      cancelBtn.addEventListener("click", () => handleCancelBooking(booking.pnr));
    }
  }

  async function handleCancelBooking(pnr) {
    if (!confirm(`Are you sure you want to cancel booking ${pnr}? This cannot be undone.`)) {
      return;
    }

    try {
      const res = await fetch(`/bookings/${pnr}/cancel`, { method: "POST" });
      const data = await res.json();

      if (res.ok) {
        showAlert(`Booking ${pnr} has been successfully cancelled. Seat is now released.`, "success");
        // Re-fetch details to refresh UI
        const updatedRes = await fetch(`/bookings/${pnr}`);
        if (updatedRes.ok) {
          renderPnrDetails(await updatedRes.json());
        }
      } else {
        showAlert(data.error || "Failed to cancel booking", "error");
      }
    } catch (err) {
      showAlert(`Error cancelling booking: ${err.message}`, "error");
    }
  }

  // ----------------------------------------------------------------------
  // Bootstrap Application
  // ----------------------------------------------------------------------
  setupDatePicker();
  checkSystemHealth();
  loadRoutes();
});

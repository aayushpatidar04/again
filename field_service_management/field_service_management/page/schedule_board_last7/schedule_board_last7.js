frappe.pages['schedule-board-last7'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Schedule Board: Last 7 Days',
		single_column: true
	});


	const pageKey = 'reload_schedule_board_last7';

    // Check if this page has been visited before
    if (!localStorage.getItem(pageKey)) {
        // If it's the first time, reload the page
        localStorage.setItem(pageKey, 'visited'); // Mark the page as visited
        window.location.reload(); // Reload the page
        return; // Exit the function to avoid further execution
    }
	localStorage.removeItem(pageKey);

	page.set_title("Schedule Board: Last 7 Days");
	frappe.call({
		method: "field_service_management.field_service_management.page.schedule_board_last7.schedule_board_last7.get_context",
		callback: function (r) {
			if (r.message) {
				$(frappe.render_template("schedule_board_last7", r.message, r.issues)).appendTo(page.body);
			} else {
				console.log("No message returned from the server.");
			}
		}
	});
	$(document).ready(function () {

		$(document).on('click', '#select-day', function () {
			var menu = $('#select-day-menu');
        
			if (menu.css('display') === 'none') {
				menu.css('display', 'block'); // Show the menu
			} else {
				menu.css('display', 'none'); // Hide the menu
			}
		});

		$(document).on('click', function (e) {
			if (!$(e.target).closest('.dropdown').length) {
				$('#select-day-menu').css('display', 'none');
			}
		});

		let liveMap = null;

		$(document).on('click', 'a[data-id]', function () {
			const modalId = $(this).data('id'); // Get the modal ID
			$(`#${modalId}`).removeClass('hide').addClass('show'); // Toggle classes

			if (modalId.startsWith('issue')) {
				const issueId = modalId.replace('issueModal', '');
				const mapContainerId = 'map-' + issueId;
				const geoDiv = $('#map-' + issueId);

				const geoDataString = geoDiv.attr('data-geo').replace(/'/g, '"');
				const geoData = JSON.parse(geoDataString);

				if (!geoDiv.length) {
					console.error('Map container not found:', mapContainerId);
					return;
				}

				if (geoDiv.data('mapInstance')) {
					geoDiv.data('mapInstance').remove();
					geoDiv.removeData('mapInstance'); // Clear the stored map instance
				}

				const map = L.map(mapContainerId).setView([10.790603876302452, 106.71873522574441], 13);
				geoDiv.data('mapInstance', map);

				frappe.call({
					method: "field_service_management.field_service_management.page.schedule_board.schedule_board.get_cords",
					callback: function (r) {
						if (r.message) {
							const technicians = r.message;

							// Check if the map container exists
							let customerLat = null;
							let customerLng = null;

							// Add shapes/markers from geoData
							geoData.forEach(feature => {
								const { properties, geometry } = feature;
								const [lng, lat] = geometry.coordinates;

								if (Object.keys(properties).length === 0) {
									customerLat = lat;
									customerLng = lng;
								} else if (properties.point_type === 'circle' && properties.radius) {
									L.circle([lat, lng], {
										radius: properties.radius,
										color: 'blue',
										fillColor: '#30a0ff',
										fillOpacity: 0.3
									}).addTo(map).bindPopup(`<b>Circle with radius: 300 meters</b>`);
								}
							});

							// Center the map on the customer's location
							if (customerLat !== null && customerLng !== null) {
								map.setView([customerLat, customerLng], 13);
								L.marker([customerLat, customerLng]).addTo(map)
									.bindPopup('<b>Customer</b><br><b>Latitude:</b> ' + customerLat + ' <b>Longitude:</b> ' + customerLng).openPopup();
							}

							// Add OpenStreetMap tiles
							L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
								maxZoom: 19,
								attribution: '&copy; OpenStreetMap contributors'
							}).addTo(map);

							// Add technician markers
							const greenIcon = L.icon({
								iconUrl: '/files/green-marker51773a.png',
								iconSize: [25, 41],
								iconAnchor: [12, 41],
								popupAnchor: [1, -34]
							});

							technicians.forEach(tech => {
								L.marker([tech.latitude, tech.longitude], { icon: greenIcon }).addTo(map)
									.bindPopup('<b>Technician: ' + tech.technician + '</b>');
							});
						} else {
							console.log("No cords returned from the server.");
						}
					}
				});
			}
		});

		$(document).on('click', '#mapModalBtn', function () { 	
			modal = $('#mapModal');
			modal.removeClass('hide').addClass('show');
			const mapContainerId = 'live-map-container';
			const mapDiv = $('#' + mapContainerId);

			// Remove existing map instance if any (to prevent re-initialization error)
			if (liveMap) {
				liveMap.remove();
				liveMap = null;
			}

			// Initialize the map
			liveMap = L.map(mapContainerId).setView([10.790603876302452, 106.71873522574441], 5); // Initial view centered on India
			L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
				maxZoom: 19,
				attribution: '&copy; OpenStreetMap contributors'
			}).addTo(liveMap);

			// Define custom icons for technicians and maintenance visits
			const technicianIcon = L.icon({
				iconUrl: '/files/green-marker51773a.png',
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34]
			});
			const greenIcon = L.icon({
				iconUrl: '/files/green-marker.png',
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34]
			});
			const yellowIcon = L.icon({
				iconUrl: '/files/yellow-marker.png',
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34]
			});
			const blueIcon = L.icon({
				iconUrl: '/files/blue-marker.png',
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34]
			});
			const redIcon = L.icon({
				iconUrl: '/files/red-marker.png',
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34]
			});
			const whiteIcon = L.icon({
				iconUrl: '/files/white-marker.png',
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34]
			});
			const blackIcon = L.icon({
				iconUrl: '/files/black-marker.png',
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34]
			});

			// Function to fetch and display locations
			function fetchAndDisplayLocations() {
				frappe.call({
					method: "field_service_management.field_service_management.page.schedule_board.schedule_board.get_live_locations",
					callback: function (r) {
						if (r.message) {
							const { technicians, maintenance } = r.message;

							// Clear existing markers before adding new ones
							liveMap.eachLayer(function (layer) {
								if (layer instanceof L.Marker) {
									liveMap.removeLayer(layer);
								}
							});

							// Add technician markers
							technicians.forEach(tech => {
								L.marker([tech.latitude, tech.longitude], { icon: technicianIcon })
									.addTo(liveMap)
									.bindPopup(`<b>Technician: ${tech.technician}</b><br>Lat: ${tech.latitude}, Lng: ${tech.longitude}`);
							});

							// Add maintenance visit markers
							maintenance.forEach(visit => {
								let customerLat = null;
								let customerLng = null;
								if (visit.geolocation && visit.geolocation.features && Array.isArray(visit.geolocation.features)) {
									visit.geolocation.features.forEach(function(feature) {
										const { properties, geometry } = feature;
										
										// Extract latitude and longitude from coordinates
										const [lng, lat] = geometry.coordinates;
								
										// Check if properties are empty
										if (Object.keys(properties).length === 0) {
											customerLat = lat;
											customerLng = lng;
										} else if (properties.point_type === 'circle' && properties.radius) {
											// Handle case for circle type with radius
											L.circle([lat, lng], {
												radius: properties.radius,
												color: 'blue',
												fillColor: '#30a0ff',
												fillOpacity: 0.3
											}).addTo(map).bindPopup(`<b>Circle with radius: ${properties.radius} meters</b>`);
										}
									});
								} else {
									console.error('Geolocation data is not in the correct format or missing');
								}
								if(visit.type == 'Unscheduled'){
									finalIcon = redIcon;
								} else if(visit.type == 'Fresh Installation'){
									finalIcon = whiteIcon;
								}else if(visit.type == 'Scheduled'){
									finalIcon = greenIcon;
								}else if(visit.type == 'Rescheduled'){
									finalIcon = blackIcon;
								}else if(visit.type == 'Site Survey'){
									finalIcon = blueIcon;
								}
								if(visit.status == 'Approval Pending'){
									finalIcon = yellowIcon;
								}
								
								if (customerLat !== null && customerLng !== null) {
									liveMap.setView([customerLat, customerLng], 13);
									L.marker([customerLat, customerLng], { icon: finalIcon })
										.addTo(liveMap)
										.bindPopup(`<b>Maintenance Visit</b><br>${visit.visit_id} - ${visit.type} - ${visit.status}<br><b>${visit.customer}</b><br>${visit.address}`);
								}
							});
						} else {
							console.log("No data returned from the server.");
						}
					}
				});
			}

			// Fetch and display the initial set of locations
			fetchAndDisplayLocations();

			// Set an interval to update locations periodically (every 30 seconds)
			updateInterval = setInterval(fetchAndDisplayLocations, 120000);
		});

		setTimeout(function () {

			var scrollableSections = $(".scrollable-x");
			$(".scrollable-x").on("scroll", function () {
				var scrollLeft = $(this).scrollLeft();
				scrollableSections.each(function () {
					if ($(this).scrollLeft() !== scrollLeft) {
						$(this).scrollLeft(scrollLeft);
					}
				});
			});
			
			$(document).on('click', '.close', function () {
				$(this).closest('.modal').removeClass('show').addClass('hide');
			});
			$('.technician').select2();

			$('.nav-link').on('click', function(event) {
				// Prevent default action
				event.preventDefault();
	
				$('.nav-link').removeClass('active');
				$('.tab-pane').removeClass('show active');
	
				$(this).addClass('active');
	
				var contentId = $(this).attr('aria-controls');
				
				$('#' + contentId ).addClass('show active');
			});
		}, 1000);

	});
}


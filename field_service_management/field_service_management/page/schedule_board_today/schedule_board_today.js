frappe.pages['schedule-board-today'].on_page_load = function (wrapper) {
   var page = frappe.ui.make_app_page({
       parent: wrapper,
       title: 'Schedule Board: Today',
       single_column: true
   });
   // This board benefits from the available planning space on wide displays.
   // Keep the wider shell scoped to this page only.
   page.container.addClass('full-width schedule-board-page-body');
   page.wrapper.find('.page-head').addClass('schedule-board-page-head');
   page.wrapper.find('.schedule-board-page-head > .container')
       .addClass('schedule-board-page-head-container');


   page.set_primary_action(__('Add Maintenance Visit'), function () {
       frappe.new_doc('Maintenance Visit');
   });


   page.set_secondary_action(__('Add Issue'), function () {
       frappe.new_doc('Issue');
   });


   const scheduleBoardRoutes = [
       { label: __('Today'), route: '/app/schedule-board-today' },
       { label: __('Yesterday'), route: '/app/schedule-board-yeste' },
       { label: __('Tomorrow'), route: '/app/schedule-tomorrow' },
       { label: __('Last 7 Days'), route: '/app/schedule-board-last7' },
       { label: __('Next 7 Days'), route: '/app/schedule-board-next7' }
   ];
   scheduleBoardRoutes.forEach(function (board) {
       page.add_inner_button(board.label, function () {
           window.location.href = board.route;
       }, __('Select Day'));
   });

   const mapAction = page.add_inner_button(__('Map'), function () {});
   mapAction.attr({
       id: 'toggle-expedition-board-map',
       'aria-label': 'Show Expedition map',
       'aria-expanded': 'false',
       title: 'Show Expedition map'
   }).addClass('schedule-board-map-toggle').removeClass('ellipsis')
       .html('<svg aria-hidden="true" viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21 3 6"></polygon><line x1="9" y1="3" x2="9" y2="18"></line><line x1="15" y1="6" x2="15" y2="21"></line></svg>');
   const selectDayGroup = page.get_inner_group_button(__('Select Day'));
   if (selectDayGroup.length) mapAction.insertBefore(selectDayGroup);




   function normalizeVisitFilterValue(value) {
       return String(value || '')
           .normalize('NFD')
           .replace(/[\u0300-\u036f]/g, '')
           .toLowerCase()
           .trim();
   }


   function applyVisitFilters() {
       const visitSearchValue = normalizeVisitFilterValue($('#visit-search-filter').val());
       const customerSearchValue = normalizeVisitFilterValue($('#customer-search-filter').val());
       const statusValue = normalizeVisitFilterValue($('#visit-status-filter').val());
       const visitTypeValue = normalizeVisitFilterValue($('#visit-type-filter').val());
       const assignmentValue = String($('#visit-assignment-filter').val() || 'unassigned');
       const territoryValue = normalizeVisitFilterValue($('#visit-territory-filter').val());
       let visibleCount = 0;


       $('.horizontal-visit-row').each(function () {
           const row = $(this);
           const rowVisitSearch = normalizeVisitFilterValue(row.attr('data-visit-search'));
           const rowPartySearch = normalizeVisitFilterValue(row.attr('data-party-search'));
           const rowStatus = normalizeVisitFilterValue(row.attr('data-completion') || 'Pending');
           const rowVisitType = normalizeVisitFilterValue(row.attr('data-visit-type'));
           const rowAssignment = String(row.attr('data-assignment') || 'unassigned');
           const rowTerritory = normalizeVisitFilterValue(row.attr('data-territory'));
           const matchesVisitSearch = !visitSearchValue || rowVisitSearch.includes(visitSearchValue);
           const matchesCustomerSearch = !customerSearchValue || rowPartySearch.includes(customerSearchValue);
           const matchesStatus = !statusValue || rowStatus === statusValue;
           const matchesVisitType = !visitTypeValue || rowVisitType === visitTypeValue;
           const matchesAssignment = assignmentValue === 'all' || rowAssignment === assignmentValue;
           const matchesTerritory = !territoryValue || rowTerritory === territoryValue;
           const isVisible = matchesVisitSearch && matchesCustomerSearch && matchesStatus
               && matchesVisitType && matchesAssignment && matchesTerritory;


           row.toggle(isVisible);
           if (isVisible) {
               visibleCount = visibleCount + 1;
           }
       });


       $('#visible-visit-count').text(visibleCount);
       $('#visit-filter-empty').toggleClass('d-none', visibleCount !== 0);
       $('#visit-list-title').text(assignmentValue === 'unassigned'
           ? 'Unassigned visits'
           : assignmentValue === 'assigned' ? 'Assigned visits' : 'Maintenance visits');
   }

   let visitQueueRequestId = 0;
   let unassignedVisitQueueMarkup = null;

   function renderQueueVisitRow(visit) {
       const name = escapeDetailsHtml(visit.name || '');
       const visitType = escapeDetailsHtml(visit.maintenance_type || 'Not specified');
       const customer = escapeDetailsHtml(visit.customer || '');
       const lead = escapeDetailsHtml(visit.custom_lead || '');
       const partyName = escapeDetailsHtml(visit.party_name || 'Not specified');
       const partyLabel = escapeDetailsHtml(visit.party_label || 'Customer');
       const completion = escapeDetailsHtml(visit.completion_status || 'Pending');
       const territory = escapeDetailsHtml(visit.territory || '');
       const visitDate = escapeDetailsHtml(visit.mntc_date || '');
       const visitTime = escapeDetailsHtml(visit.mntc_time_display || '');
       const assigned = Boolean(visit.is_assigned);
       const assignedDisplay = escapeDetailsHtml(visit.assigned_display || '');
       const statusOptions = Array.from(document.querySelectorAll('#visit-status-filter option'))
           .filter((option) => option.value)
           .map((option) => ({ value: option.value, label: option.textContent.trim() }));
       if (!statusOptions.some((option) => option.value === completion)) {
           statusOptions.unshift({ value: completion, label: completion });
       }
       const statusMarkup = visit.can_write
           ? statusOptions.map((option) => `<option value="${escapeDetailsHtml(option.value)}"${option.value === completion ? ' selected' : ''}>${escapeDetailsHtml(option.label)}</option>`).join('')
           : `<option value="${completion}" selected>${completion}</option>`;
       const partyLink = customer
           ? `<a href="/app/customer/${customer}" target="_blank" rel="noopener">${partyName}</a>`
           : lead
               ? `<a href="/app/lead/${lead}" target="_blank" rel="noopener">${partyName}</a>`
               : partyName;

       return `<div class="horizontal-visit-row ${assigned ? '' : 'drag'} maintenance-visit-card" data-type="type1" data-completion="${completion}" data-visit-type="${visitType}" data-assignment="${assigned ? 'assigned' : 'unassigned'}" data-visit-date="${visitDate}" data-territory="${territory}" data-visit-search="${name} ${visitType}" data-party-search="${partyName} ${partyLabel}" data-issue="${name}" draggable="${assigned ? 'false' : 'true'}" id="${name}"><div class="horizontal-visit-subject" title="${visitType}"><strong>${visitType}</strong><span class="horizontal-visit-meta">${name}</span>${assigned ? `<span class="horizontal-visit-meta">Assigned · ${assignedDisplay}</span>` : ''}</div><div class="horizontal-visit-party" title="${partyName}">${partyLink}<span class="horizontal-visit-meta">${partyLabel}</span></div><div>${visitDate || 'Not scheduled'}<span class="horizontal-visit-meta">${visitTime}</span></div><div><select class="horizontal-status-pill board-row-completion" data-visit="${name}" aria-label="${visit.can_write ? 'Change' : 'Completion'} status for ${name}" draggable="false"${visit.can_write ? '' : ' disabled'}>${statusMarkup}</select></div><div class="horizontal-visit-actions">${assigned ? '' : `<button type="button" class="assign-visit" data-visit="${name}" aria-label="Assign ${name}" title="Assign this visit without dragging" draggable="false">Assign</button>`}<button type="button" class="create-visit-issue" data-visit="${name}" data-customer="${customer}" aria-label="Create issue for ${name}" title="Create issue for this visit" draggable="false">+ Issue</button></div></div>`;
   }

   function loadVisitQueueAssignment(assignmentStatus) {
       const list = document.querySelector('#maintenance-tab-body .horizontal-visit-list');
       if (!list) return;
       const requestId = ++visitQueueRequestId;
       const currentRows = Array.from(list.querySelectorAll('.horizontal-visit-row'));
       if (currentRows.length && currentRows.every((row) => row.dataset.assignment === 'unassigned')) {
           unassignedVisitQueueMarkup = list.innerHTML;
       }
       if (unassignedVisitQueueMarkup === null) unassignedVisitQueueMarkup = list.innerHTML;
       if (assignmentStatus === 'unassigned') {
           list.innerHTML = unassignedVisitQueueMarkup;
           applyVisitFilters();
           return;
       }

       const rowsContainer = list.querySelectorAll('.horizontal-visit-row');
       rowsContainer.forEach((row) => row.remove());
       $('#visible-visit-count').text('…');
       frappe.call({
           method: 'field_service_management.field_service_management.page.api.get_schedule_board_queue_rows',
           args: { assignment_status: assignmentStatus },
           callback: function (response) {
               if (requestId !== visitQueueRequestId) return;
               const rows = Array.isArray(response.message) ? response.message : [];
               const header = list.querySelector('.horizontal-visit-header');
               if (header && rows.length) header.insertAdjacentHTML('afterend', rows.map(renderQueueVisitRow).join(''));
               applyVisitFilters();
           },
           error: function () {
               if (requestId !== visitQueueRequestId) return;
               frappe.show_alert({ message: __('Could not load assigned visits. Please try again.'), indicator: 'red' });
               list.innerHTML = unassignedVisitQueueMarkup;
               $('#visit-assignment-filter').val('unassigned');
               applyVisitFilters();
           },
       });
   }

   function setVisitPanelHeight(height) {
       const stack = $('.board-sections-stack').get(0);
       if (!stack) return;
       const minimumHeight = 190;
       const minimumCalendarHeight = $('.schedule-board-workspace').hasClass('is-map-open') ? 220 : 368;
       const maximumHeight = Math.min(480, stack.clientHeight - minimumCalendarHeight);
       if (maximumHeight < minimumHeight) return;

       const safeHeight = Math.max(minimumHeight, Math.min(maximumHeight, height));
       stack.style.setProperty('--visits-panel-height', safeHeight + 'px');
       $('#visit-calendar-resizer')
           .attr('aria-valuemin', minimumHeight)
           .attr('aria-valuemax', Math.round(maximumHeight))
           .attr('aria-valuenow', Math.round(safeHeight));
       try {
           localStorage.setItem('schedule-board-today-visits-panel-height-v2', String(Math.round(safeHeight)));
       } catch (error) {
           // Keep resizing available when browser storage is disabled.
       }
   }

   function restoreVisitPanelHeight() {
       let savedHeight = 380;
       try {
           const storedHeight = Number(localStorage.getItem('schedule-board-today-visits-panel-height-v2'));
           if (Number.isFinite(storedHeight) && storedHeight > 0) savedHeight = storedHeight;
       } catch (error) {
           // Use the default height when browser storage is disabled.
       }
       setVisitPanelHeight(savedHeight);
   }

   function hydrateTechnicianAvatars() {
       $('.schedule-user-avatar-slot').each(function () {
           const slot = $(this);
           const name = String(slot.attr('data-technician-name') || '').trim();
           slot.find('.schedule-user-avatar-fallback').text(name.charAt(0) || '?');

           const image = slot.find('.schedule-user-avatar');
           const hideBrokenImage = function () {
               image.prop('hidden', true);
           };
           image.on('error', hideBrokenImage);
           if (image.length && image.get(0).complete && image.get(0).naturalWidth === 0) {
               hideBrokenImage();
           }
       });
   }


   page.set_title("Schedule Board: Today");

   const liveTechnicianSourceId = 'bms-live-technician-source';
   const liveTechnicianCircleLayerId = 'bms-live-technician-circles';
   const liveTechnicianDomOverlayClass = 'bms-live-technician-overlay';
   const mapVisitDomOverlayClass = 'bms-maintenance-visit-overlay';
   // Colours are allocated as technicians arrive rather than being restricted to
   // a fixed palette. The golden-angle sequence keeps even large groups distinct.
   const technicianMarkerColors = new Map();
   const visitTypeColors = new Map();
   const hiddenMapVisitTypes = new Set();
   let liveTechnicianPoll = null;
   let liveTechnicianMapWait = null;
   let liveTechnicianMap = null;
   let liveTechnicianFetchInFlight = false;
   let liveTechnicianStyleHandler = null;
   let liveTechnicianFeatures = [];
   let techniciansVisibleOnMap = true;
   let mapVisitFeatures = [];
   let configuredMapVisitTypes = [];
   let mapVisitsRequestId = 0;
   let selectedMapDateRange = 'today';
   let vietnamInitialViewportSet = false;
   let nativeTodayBoardLayerNames = [];
   let nativeTodayBoardLayers = [];

   function refreshNativeTodayBoardLayers() {
       const range = getMapDateRange(selectedMapDateRange);
       nativeTodayBoardLayerNames.forEach(function (layerName) {
           window.dispatchEvent(new CustomEvent('expedition:refresh-layer', {
               detail: {
                   layerName: layerName,
                   context: { map_start_date: range.start, map_end_date: range.end },
               },
           }));
       });
   }

   function setTechnicianLocationStatus(message, state) {
       const status = document.getElementById('technician-live-location-status');
       if (!status) return;
       status.textContent = message;
       status.dataset.state = state || 'idle';
   }

   function markerColor(feature) {
       const key = String(feature.properties?.technician || feature.properties?.name || 'technician').trim().toLowerCase();
       if (!technicianMarkerColors.has(key)) {
           const goldenAngle = 137.50776405003785;
           const hue = Math.round((technicianMarkerColors.size * goldenAngle) % 360);
           technicianMarkerColors.set(key, `hsl(${hue} 78% 42%)`);
       }
       return technicianMarkerColors.get(key);
   }

   function visitTypeColor(visitType) {
       const key = String(visitType || 'Not specified').trim().toLowerCase();
       if (!visitTypeColors.has(key)) {
           const goldenAngle = 137.50776405003785;
           const hue = Math.round(((visitTypeColors.size + 2) * goldenAngle) % 360);
           visitTypeColors.set(key, `hsl(${hue} 78% 40%)`);
       }
       return visitTypeColors.get(key);
   }

   function getVisitCoordinates(visit) {
       let geolocation = visit?.geolocation;
       if (typeof geolocation === 'string') {
           try {
               geolocation = JSON.parse(geolocation);
           } catch (error) {
               return null;
           }
       }
       const features = Array.isArray(geolocation?.features) ? geolocation.features : [];
       for (const feature of features) {
           const coordinates = feature?.geometry?.coordinates;
           const properties = feature?.properties || {};
           if (feature?.geometry?.type !== 'Point' || properties.point_type === 'circle'
               || !Array.isArray(coordinates) || coordinates.length < 2) continue;
           const longitude = Number(coordinates[0]);
           const latitude = Number(coordinates[1]);
           if (Number.isFinite(latitude) && Number.isFinite(longitude)
               && latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180) {
               return [longitude, latitude];
           }
       }
       return null;
   }

   function normalizeMapVisits(rows) {
       const allowedTypes = new Set(configuredMapVisitTypes);
       return (Array.isArray(rows) ? rows : []).reduce(function (features, visit) {
           if (!allowedTypes.has(String(visit.type || ''))) return features;
           const coordinates = getVisitCoordinates(visit);
           if (!coordinates) return features;
           features.push({
               type: 'Feature',
               geometry: { type: 'Point', coordinates },
               properties: {
                   visit_id: String(visit.visit_id || ''),
                   type: String(visit.type || 'Not specified'),
                   status: String(visit.status || 'Pending'),
                   customer: String(visit.customer || ''),
                   address: String(visit.address || ''),
               },
           });
           return features;
       }, []);
   }

   function renderMapVisitTypeFilters(features) {
       const filterBar = document.getElementById('map-visit-type-filters');
       const options = document.getElementById('map-visit-type-filter-options');
       if (!filterBar || !options) return;
       const types = Array.from(new Set([
           ...configuredMapVisitTypes,
           ...(Array.isArray(features) ? features : []).map(function (feature) {
               return feature.properties?.type || 'Not specified';
           }),
       ].filter(Boolean))).sort(function (left, right) { return left.localeCompare(right); });
       filterBar.hidden = false;
       options.textContent = '';
       const technicianButton = document.createElement('button');
       technicianButton.type = 'button';
       technicianButton.className = 'map-visit-type-filter map-technician-layer-filter';
       technicianButton.dataset.mapLayer = 'technicians';
       technicianButton.setAttribute('aria-pressed', String(techniciansVisibleOnMap));
       technicianButton.title = `${techniciansVisibleOnMap ? 'Hide' : 'Show'} technician locations`;
       technicianButton.style.setProperty('--visit-type-colour', '#2563eb');
       const technicianColour = document.createElement('span');
       technicianColour.className = 'map-visit-type-colour';
       technicianColour.setAttribute('aria-hidden', 'true');
       const technicianLabel = document.createElement('span');
       technicianLabel.textContent = 'Technicians';
       technicianButton.append(technicianColour, technicianLabel);
       options.appendChild(technicianButton);
       types.forEach(function (type) {
           const enabled = !hiddenMapVisitTypes.has(type);
           const button = document.createElement('button');
           button.type = 'button';
           button.className = 'map-visit-type-filter';
           button.dataset.visitType = type;
           button.setAttribute('aria-pressed', String(enabled));
           button.title = `${enabled ? 'Hide' : 'Show'} ${type} visits`;
           button.style.setProperty('--visit-type-colour', visitTypeColor(type));
           const colour = document.createElement('span');
           colour.className = 'map-visit-type-colour';
           colour.setAttribute('aria-hidden', 'true');
           const label = document.createElement('span');
           label.textContent = type;
           button.append(colour, label);
           options.appendChild(button);
       });
   }

   function openMapVisit(feature) {
       const visitId = feature?.properties?.visit_id;
       if (!visitId) return;
       const row = Array.from(document.querySelectorAll('.horizontal-visit-row')).find(function (element) {
           return element.getAttribute('data-issue') === visitId;
       });
       if (row) {
           row.click();
           return;
       }
       frappe.set_route('Form', 'Maintenance Visit', visitId);
   }

   function renderMapVisitDomMarkers(map, features) {
       const container = map?.getContainer?.();
       if (!container) return false;
       mapVisitFeatures = Array.isArray(features) ? features : mapVisitFeatures;
       let overlay = container.querySelector(`.${mapVisitDomOverlayClass}`);
       if (!overlay) {
           overlay = document.createElement('div');
           overlay.className = mapVisitDomOverlayClass;
           overlay.style.cssText = 'position:absolute;inset:0;z-index:4;pointer-events:none;overflow:hidden;';
           container.appendChild(overlay);
       }
       overlay.textContent = '';
       mapVisitFeatures.filter(function (feature) {
           return !hiddenMapVisitTypes.has(feature.properties?.type || 'Not specified');
       }).forEach(function (feature) {
           const point = map.project(feature.geometry.coordinates);
           const properties = feature.properties || {};
           const colour = visitTypeColor(properties.type);
           const marker = document.createElement('button');
           marker.type = 'button';
           marker.setAttribute('aria-label', `Open Maintenance Visit ${properties.visit_id || ''}`);
           marker.title = `${properties.visit_id || 'Maintenance Visit'} · ${properties.type || 'Not specified'} · ${properties.status || 'Pending'}`;
           marker.style.cssText = `background:transparent;border:0;cursor:pointer;display:block;left:${point.x}px;padding:0;pointer-events:auto;position:absolute;top:${point.y}px;transform:translate(-50%,-100%);`;
           const pin = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
           pin.setAttribute('viewBox', '0 0 24 32');
           pin.setAttribute('width', '25');
           pin.setAttribute('height', '34');
           pin.style.cssText = 'display:block;filter:drop-shadow(0 2px 3px rgba(15,23,42,.38));';
           const pinBody = document.createElementNS('http://www.w3.org/2000/svg', 'path');
           pinBody.setAttribute('fill', colour);
           pinBody.setAttribute('d', 'M12 0C5.37 0 0 5.37 0 12c0 8.88 12 20 12 20s12-11.12 12-20C24 5.37 18.63 0 12 0Z');
           const pinCenter = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
           pinCenter.setAttribute('cx', '12');
           pinCenter.setAttribute('cy', '12');
           pinCenter.setAttribute('r', '4.6');
           pinCenter.setAttribute('fill', '#fff');
           pin.append(pinBody, pinCenter);
           marker.appendChild(pin);
           marker.addEventListener('click', function (event) {
               event.preventDefault();
               event.stopPropagation();
               openMapVisit(feature);
           });
           overlay.appendChild(marker);
       });
       if (!map.__bmsMapVisitDomRenderBound) {
           const redraw = function () { renderMapVisitDomMarkers(map, mapVisitFeatures); };
           map.on('move', redraw);
           map.on('resize', redraw);
           map.__bmsMapVisitDomRenderBound = true;
       }
       return true;
   }

   function markerTime(feature) {
       const value = feature.properties.time ? new Date(feature.properties.time) : null;
       return value && Number.isFinite(value.getTime())
           ? value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
           : 'time unavailable';
   }

   function populateMapTechnicianSearchOptions(features) {
       const options = document.getElementById('map-technician-search-options');
       if (!options) return;
       const values = new Set();
       (Array.isArray(features) ? features : []).forEach(function (feature) {
           const properties = feature.properties || {};
           if (properties.name) values.add(String(properties.name));
           if (properties.technician) values.add(String(properties.technician));
       });
       options.textContent = '';
       Array.from(values).sort(function (left, right) {
           return left.localeCompare(right);
       }).forEach(function (value) {
           const option = document.createElement('option');
           option.value = value;
           options.appendChild(option);
       });
   }

   function findMapTechnician(query) {
       const normalizedQuery = String(query || '').trim().toLowerCase();
       if (!normalizedQuery) return null;
       const searchableValue = function (feature) {
           const properties = feature.properties || {};
           return `${properties.name || ''} ${properties.technician || ''}`.toLowerCase();
       };
       const exact = liveTechnicianFeatures.find(function (feature) {
           const properties = feature.properties || {};
           return String(properties.name || '').toLowerCase() === normalizedQuery
               || String(properties.technician || '').toLowerCase() === normalizedQuery;
       });
       return exact || liveTechnicianFeatures.find(function (feature) {
           return searchableValue(feature).startsWith(normalizedQuery);
       }) || liveTechnicianFeatures.find(function (feature) {
           return searchableValue(feature).includes(normalizedQuery);
       }) || null;
   }

   function focusMapTechnician(feature) {
       const map = window.expeditionMap?.getMap?.();
       const coordinates = feature?.geometry?.coordinates;
       if (!map || !Array.isArray(coordinates) || coordinates.length !== 2) return false;
       if (typeof map.flyTo === 'function') {
           map.flyTo({ center: coordinates, zoom: Math.max(Number(map.getZoom?.()) || 0, 13), duration: 750 });
       } else {
           map.setCenter?.(coordinates);
           map.setZoom?.(13);
       }
       showTechnicianMarkerDetail(feature);
       return true;
   }

   function locateMapTechnician(showFeedback) {
       const input = document.getElementById('map-technician-search');
       if (!input) return;
       const query = input.value.trim();
       if (!query) {
           input.removeAttribute('aria-invalid');
           return;
       }
       const feature = findMapTechnician(query);
       if (feature && focusMapTechnician(feature)) {
           input.removeAttribute('aria-invalid');
           return;
       }
       input.setAttribute('aria-invalid', 'true');
       if (showFeedback) frappe.show_alert({ message: __('No matching technician location found'), indicator: 'orange' });
   }

   function showTechnicianMarkerDetail(feature) {
       const properties = feature.properties || {};
       const demoNote = properties.is_demo ? ' · DEMO LOCATION' : '';
       setTechnicianLocationStatus(
           `${properties.technician || properties.name || 'Technician'} · last GPS update ${markerTime(feature)}${demoNote}`,
           properties.is_demo ? 'demo' : (properties.is_fresh ? 'live' : 'stale')
       );
   }

   function renderLiveTechnicianDomMarkers(map, features) {
       const container = map?.getContainer?.();
       if (!container) return false;
       liveTechnicianFeatures = Array.isArray(features) ? features : liveTechnicianFeatures;
       let overlay = container.querySelector(`.${liveTechnicianDomOverlayClass}`);
       if (!overlay) {
           overlay = document.createElement('div');
           overlay.className = liveTechnicianDomOverlayClass;
           overlay.style.cssText = 'position:absolute;inset:0;z-index:5;pointer-events:none;overflow:hidden;';
           container.appendChild(overlay);
       }

       overlay.textContent = '';
       if (!techniciansVisibleOnMap) return true;
       liveTechnicianFeatures.forEach(function (feature) {
           const point = map.project(feature.geometry.coordinates);
           const properties = feature.properties || {};
           const technicianId = properties.technician || properties.name || 'Technician';
           const marker = document.createElement('button');
           marker.type = 'button';
           marker.setAttribute('aria-label', `Show ${technicianId} location details`);
           marker.title = `${technicianId} · ${markerTime(feature)}${properties.is_demo ? ' · Demo location' : ''}`;
           marker.style.cssText = [
               'background:transparent',
               'border:0',
               'cursor:pointer',
               'display:block',
               `left:${point.x}px`,
               'padding:0',
               'pointer-events:auto',
               'position:absolute',
               `top:${point.y}px`,
               'transform:translate(-50%,-50%)',
               'white-space:nowrap',
           ].join(';');

           // Technicians use a hard-hat/service glyph, while Maintenance Visits
           // remain teardrop pins. Their background is still colour-coded per user.
           const technicianIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
           technicianIcon.setAttribute('viewBox', '0 0 44 44');
           technicianIcon.setAttribute('width', '38');
           technicianIcon.setAttribute('height', '38');
           technicianIcon.style.cssText = 'display:block;filter:drop-shadow(0 2px 3px rgba(15,23,42,.38));';
           const iconBackground = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
           iconBackground.setAttribute('cx', '22');
           iconBackground.setAttribute('cy', '22');
           iconBackground.setAttribute('r', '18');
           iconBackground.setAttribute('fill', markerColor(feature));
           iconBackground.setAttribute('stroke', '#ffffff');
           iconBackground.setAttribute('stroke-width', '3');
           const hardHat = document.createElementNS('http://www.w3.org/2000/svg', 'path');
           hardHat.setAttribute('d', 'M11 18c0-5.7 4.5-10 10.5-10S32 12.3 32 18H11Zm-2 1h25v3H9z');
           hardHat.setAttribute('fill', '#ffffff');
           const face = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
           face.setAttribute('cx', '21.5');
           face.setAttribute('cy', '24');
           face.setAttribute('r', '5');
           face.setAttribute('fill', '#ffffff');
           const body = document.createElementNS('http://www.w3.org/2000/svg', 'path');
           body.setAttribute('d', 'M11 38c.8-6.3 5-9.5 10.5-9.5S31.2 31.7 32 38H11Z');
           body.setAttribute('fill', '#ffffff');
           const wrench = document.createElementNS('http://www.w3.org/2000/svg', 'path');
           wrench.setAttribute('d', 'm31.7 27.4 5.3 5.3m-3.7-7.1a3.2 3.2 0 0 0 3.8 3.8l-3.4 3.4a3.2 3.2 0 0 0-3.8-3.8l3.4-3.4Z');
           wrench.setAttribute('fill', 'none');
           wrench.setAttribute('stroke', '#ffffff');
           wrench.setAttribute('stroke-linecap', 'round');
           wrench.setAttribute('stroke-linejoin', 'round');
           wrench.setAttribute('stroke-width', '2.2');
           technicianIcon.append(iconBackground, hardHat, face, body, wrench);
           const label = document.createElement('span');
           label.textContent = technicianId;
           label.style.cssText = `background:rgba(255,255,255,.96);border-left:3px solid ${markerColor(feature)};border-radius:5px;box-shadow:0 1px 4px rgba(15,23,42,.2);color:#0f172a;font:600 11px/1.2 system-ui,sans-serif;left:28px;padding:3px 5px;position:absolute;text-shadow:none;top:-4px;`;
           marker.append(technicianIcon, label);
           marker.addEventListener('click', function (event) {
               event.preventDefault();
               event.stopPropagation();
               showTechnicianMarkerDetail(feature);
           });
           overlay.appendChild(marker);
       });
       if (!map.__bmsLiveTechnicianDomRenderBound) {
           const redraw = function () {
               renderLiveTechnicianDomMarkers(map, liveTechnicianFeatures);
           };
           map.on('move', redraw);
           map.on('resize', redraw);
           map.__bmsLiveTechnicianDomRenderBound = true;
       }
       return true;
   }

   function ensureLiveTechnicianLayers(map) {
       if (!map || !map.getContainer?.()) return false;
       try {
           // DOM pins are independent of Expedition's map-style lifecycle.
           // Hide an older GeoJSON circle overlay if this page was opened
           // before the pin implementation was loaded.
           if (!map.getLayer(liveTechnicianCircleLayerId)) {
               return true;
           }
           map.setLayoutProperty(liveTechnicianCircleLayerId, 'visibility', 'none');
           return true;
       } catch (error) {
           console.warn('Unable to add live technician locations to Expedition:', error);
           // The board also renders DOM pins above the map. A failed optional
           // GeoJSON source/layer must not stop the GPS feed or those pins.
           return true;
       }
   }

   function normalizeTechnicianLocations(rows) {
       const now = Date.now();
       return (Array.isArray(rows) ? rows : []).reduce((features, row) => {
           const latitude = Number(row.latitude);
           const longitude = Number(row.longitude);
           if (!Number.isFinite(latitude) || !Number.isFinite(longitude)
               || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return features;

           const name = String(row.technician_name || row.technician || 'Technician');
           const timestamp = row.time ? new Date(row.time) : null;
           const ageMs = timestamp && Number.isFinite(timestamp.getTime()) ? now - timestamp.getTime() : Infinity;
           features.push({
               type: 'Feature',
               geometry: { type: 'Point', coordinates: [longitude, latitude] },
               properties: {
                   technician: String(row.technician || ''),
                   name,
                   time: row.time ? String(row.time) : '',
                   is_fresh: ageMs >= 0 && ageMs <= 15 * 60 * 1000,
                   is_demo: Boolean(Number(row.is_mocked)) || String(row.location_source || '').toLowerCase().includes('demo'),
               },
           });
           return features;
       }, []);
   }

   function refreshLiveTechnicianLocations() {
       if (document.getElementById('expedition-board-map-section')?.hidden) return;
       const map = window.expeditionMap?.getMap?.();
       if (!map || !ensureLiveTechnicianLayers(map)) return;
       // Expedition owns data retrieval for the native Technician layer.
       // Reading that layer removes the old duplicate request and guarantees
       // Locate, status, pins, and native visibility controls use one feed.
       refreshNativeTodayBoardLayers();
       const technicianLayer = nativeTodayBoardLayers.find(function (layer) {
           return /technician|user|live location/i.test(String(layer.title || ''));
       });
       const technicianLayerName = technicianLayer?.name || nativeTodayBoardLayerNames[0];
       window.setTimeout(function () {
           const features = window.Expedition?.getLayerFeatures?.(technicianLayerName) || [];
           liveTechnicianFeatures = Array.isArray(features) ? features : [];
           populateMapTechnicianSearchOptions(liveTechnicianFeatures);
           if (!liveTechnicianFeatures.length) {
               setTechnicianLocationStatus('Waiting for technician GPS locations', 'idle');
               return;
           }
           setTechnicianLocationStatus(
               `${liveTechnicianFeatures.length} technician location${liveTechnicianFeatures.length === 1 ? '' : 's'} loaded`,
               'live'
           );
       }, 450);
   }

   function refreshMapMaintenanceVisits(attempt) {
       if (document.getElementById('expedition-board-map-section')?.hidden) return;
       const map = window.expeditionMap?.getMap?.();
       if (!map) {
           if ((attempt || 0) < 20) {
               window.setTimeout(function () { refreshMapMaintenanceVisits((attempt || 0) + 1); }, 200);
           }
           return;
       }
       const requestId = ++mapVisitsRequestId;
       const range = getMapDateRange(selectedMapDateRange);
       frappe.call({
           method: 'field_service_management.field_service_management.page.api.get_map_maintenance_visits',
           args: { start_date: range.start, end_date: range.end },
           callback: function (response) {
               if (requestId !== mapVisitsRequestId) return;
               const features = normalizeMapVisits(response.message);
               mapVisitFeatures = features;
               renderMapVisitTypeFilters(features);
               renderMapVisitDomMarkers(map, features);
               refreshNativeTodayBoardLayers();
               const summary = document.getElementById('map-date-range-summary');
               if (summary) summary.textContent = `${range.label} · ${features.length} visit${features.length === 1 ? '' : 's'}`;
           },
           error: function (error) {
               if (requestId !== mapVisitsRequestId) return;
               console.warn('Unable to fetch Maintenance Visit map locations:', error);
               const summary = document.getElementById('map-date-range-summary');
               if (summary) summary.textContent = `${range.label} · unable to load route plan`;
           },
       });
   }

   function localDateString(date) {
       return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
   }

   function getMapDateRange(rangeKey) {
       const boardDate = String($('#schedule-board-workspace').attr('data-board-date') || '');
       const parts = boardDate.split('-').map(Number);
       const today = parts.length === 3 && parts.every(Number.isFinite)
           ? new Date(parts[0], parts[1] - 1, parts[2])
           : new Date();
       today.setHours(0, 0, 0, 0);
       const offset = function (days) {
           const date = new Date(today);
           date.setDate(date.getDate() + days);
           return date;
       };
       const ranges = {
           today: { start: offset(0), end: offset(0), label: 'Today' },
           tomorrow: { start: offset(1), end: offset(1), label: 'Tomorrow' },
           yesterday: { start: offset(-1), end: offset(-1), label: 'Yesterday' },
           next7: { start: offset(0), end: offset(6), label: 'Next 7 days' },
           last7: { start: offset(-6), end: offset(0), label: 'Last 7 days' },
       };
       const selected = ranges[rangeKey] || ranges.today;
       return {
           start: localDateString(selected.start),
           end: localDateString(selected.end),
           label: selected.label,
       };
   }

   function refreshConfiguredMapVisitTypes() {
       frappe.call({
           method: 'field_service_management.field_service_management.page.api.get_map_maintenance_visit_types',
           callback: function (response) {
               configuredMapVisitTypes = Array.isArray(response.message)
                   ? response.message.map(String)
                   : [];
               renderMapVisitTypeFilters(mapVisitFeatures);
           },
           error: function (error) {
               console.warn('Unable to fetch configured Maintenance Visit types:', error);
           },
       });
   }

   function startLiveTechnicianLocations() {
       if (liveTechnicianPoll) return;
       let attempts = 0;
       liveTechnicianMapWait = window.setInterval(function () {
           const map = window.expeditionMap?.getMap?.();
           attempts += 1;
           if (map && ensureLiveTechnicianLayers(map)) {
               window.clearInterval(liveTechnicianMapWait);
               liveTechnicianMapWait = null;
               if (!vietnamInitialViewportSet && typeof map.fitBounds === 'function') {
                   map.fitBounds([[101.5, 7.5], [110.5, 24]], {
                       padding: { top: 48, right: 48, bottom: 48, left: 48 },
                       maxZoom: 6,
                       duration: 700,
                   });
                   vietnamInitialViewportSet = true;
               }
               if (liveTechnicianMap !== map) {
                   if (liveTechnicianMap && liveTechnicianStyleHandler) {
                       liveTechnicianMap.off('styledata', liveTechnicianStyleHandler);
                   }
                   liveTechnicianMap = map;
                   liveTechnicianStyleHandler = function () {
                       if (!document.getElementById('expedition-board-map-section')?.hidden
                           && ensureLiveTechnicianLayers(map)) refreshLiveTechnicianLocations();
                   };
                   map.on('styledata', liveTechnicianStyleHandler);
               }
               refreshLiveTechnicianLocations();
               liveTechnicianPoll = window.setInterval(refreshLiveTechnicianLocations, 30 * 1000);
           } else if (attempts >= 80) {
               window.clearInterval(liveTechnicianMapWait);
               liveTechnicianMapWait = null;
               setTechnicianLocationStatus('Map is ready, waiting for GPS locations', 'idle');
           }
       }, 250);
   }

   function stopLiveTechnicianLocations() {
       if (liveTechnicianPoll) window.clearInterval(liveTechnicianPoll);
       if (liveTechnicianMapWait) window.clearInterval(liveTechnicianMapWait);
       liveTechnicianPoll = null;
       liveTechnicianMapWait = null;
   }

   window.addEventListener('beforeunload', stopLiveTechnicianLocations);

   function setupMapLayerDockDrag(host) {
       const dock = document.getElementById('map-visit-type-filters');
       if (!host || !dock || dock.dataset.dragInitialized === '1') return;
       dock.dataset.dragInitialized = '1';
       let activePointerId = null;
       let origin = null;
       const clampPosition = function (left, top) {
           const maxLeft = Math.max(8, host.clientWidth - dock.offsetWidth - 8);
           const maxTop = Math.max(8, host.clientHeight - dock.offsetHeight - 8);
           return {
               left: Math.max(8, Math.min(maxLeft, left)),
               top: Math.max(8, Math.min(maxTop, top)),
           };
       };
       const setPosition = function (left, top) {
           const position = clampPosition(left, top);
           dock.style.bottom = 'auto';
           dock.style.left = position.left + 'px';
           dock.style.top = position.top + 'px';
           dock.style.transform = 'none';
           return position;
       };
       window.requestAnimationFrame(function () {
           try {
               const savedPosition = JSON.parse(localStorage.getItem('schedule-board-today-map-layer-dock') || '{}');
               if (Number.isFinite(savedPosition.left) && Number.isFinite(savedPosition.top)) {
                   setPosition(savedPosition.left, savedPosition.top);
               }
           } catch (error) {
               // Keep the default bottom-centre position if storage is unavailable.
           }
       });
       dock.addEventListener('pointerdown', function (event) {
           if (event.button !== 0 || event.target.closest('button')) return;
           const hostRect = host.getBoundingClientRect();
           const dockRect = dock.getBoundingClientRect();
           const position = setPosition(dockRect.left - hostRect.left, dockRect.top - hostRect.top);
           activePointerId = event.pointerId;
           origin = { x: event.clientX, y: event.clientY, left: position.left, top: position.top };
           dock.classList.add('is-dragging');
           dock.setPointerCapture(event.pointerId);
           event.preventDefault();
       });
       dock.addEventListener('pointermove', function (event) {
           if (activePointerId !== event.pointerId || !origin) return;
           setPosition(origin.left + event.clientX - origin.x, origin.top + event.clientY - origin.y);
       });
       const stopDragging = function (event) {
           if (activePointerId !== event.pointerId) return;
           activePointerId = null;
           origin = null;
           dock.classList.remove('is-dragging');
           try {
               localStorage.setItem('schedule-board-today-map-layer-dock', JSON.stringify({
                   left: Math.round(parseFloat(dock.style.left) || 8),
                   top: Math.round(parseFloat(dock.style.top) || 8),
               }));
           } catch (error) {
               // Dragging remains usable when browser storage is unavailable.
           }
       };
       dock.addEventListener('pointerup', stopDragging);
       dock.addEventListener('pointercancel', stopDragging);
   }

   function setupNativeLegendDrag(host, attempts) {
       const legendDock = host?.querySelector?.('.expedition__bc');
       if (!legendDock) {
           if ((attempts || 0) < 20) {
               window.setTimeout(function () { setupNativeLegendDrag(host, (attempts || 0) + 1); }, 150);
           }
           return;
       }
       if (legendDock.dataset.boardDragInitialized === '1') return;
       legendDock.dataset.boardDragInitialized = '1';
       let pointerId = null;
       let origin = null;
       const clamp = function (left, top) {
           return {
               left: Math.max(10, Math.min(host.clientWidth - legendDock.offsetWidth - 10, left)),
               top: Math.max(10, Math.min(host.clientHeight - legendDock.offsetHeight - 10, top)),
           };
       };
       const moveTo = function (left, top) {
           const point = clamp(left, top);
           legendDock.style.setProperty('--board-legend-left', `${point.left}px`);
           legendDock.style.setProperty('--board-legend-top', `${point.top}px`);
           legendDock.classList.add('is-board-dragged');
           return point;
       };
       try {
           const saved = JSON.parse(localStorage.getItem('schedule-board-today-native-legend') || '{}');
           if (Number.isFinite(saved.left) && Number.isFinite(saved.top)) moveTo(saved.left, saved.top);
       } catch (error) {
           // The default bottom-centre placement remains available.
       }
       legendDock.addEventListener('pointerdown', function (event) {
           if (event.button !== 0 || event.target.closest('button')) return;
           const hostRect = host.getBoundingClientRect();
           const dockRect = legendDock.getBoundingClientRect();
           const point = moveTo(dockRect.left - hostRect.left, dockRect.top - hostRect.top);
           pointerId = event.pointerId;
           origin = { x: event.clientX, y: event.clientY, left: point.left, top: point.top };
           legendDock.setPointerCapture(event.pointerId);
           event.preventDefault();
       });
       legendDock.addEventListener('pointermove', function (event) {
           if (pointerId !== event.pointerId || !origin) return;
           moveTo(origin.left + event.clientX - origin.x, origin.top + event.clientY - origin.y);
       });
       const finish = function (event) {
           if (pointerId !== event.pointerId) return;
           pointerId = null;
           origin = null;
           try {
               localStorage.setItem('schedule-board-today-native-legend', JSON.stringify({
                   left: Math.round(parseFloat(legendDock.style.getPropertyValue('--board-legend-left')) || 10),
                   top: Math.round(parseFloat(legendDock.style.getPropertyValue('--board-legend-top')) || 10),
               }));
           } catch (error) {
               // Dragging works even if storage is unavailable.
           }
       };
       legendDock.addEventListener('pointerup', finish);
       legendDock.addEventListener('pointercancel', finish);
       if (typeof ResizeObserver === 'function') {
           const keepLegendVisible = new ResizeObserver(function () {
               if (pointerId !== null || !host.clientWidth || !host.clientHeight ||
                   !legendDock.classList.contains('is-board-dragged')) return;
               moveTo(
                   parseFloat(legendDock.style.getPropertyValue('--board-legend-left')),
                   parseFloat(legendDock.style.getPropertyValue('--board-legend-top'))
               );
           });
           keepLegendVisible.observe(host);
           keepLegendVisible.observe(legendDock);
       }
   }

   async function mountExpeditionBoardMap() {
       const host = document.getElementById('expedition-board-map-host');
       if (!host) return;
       if (host.dataset.expeditionMounted === '1') {
           setupNativeLegendDrag(host);
           return;
       }
       if (host.dataset.expeditionMountStarted === '1') return;
       host.dataset.expeditionMountStarted = '1';
       host.textContent = 'Loading Expedition map...';

       try {
           await frappe.require([
               '/assets/expedition/dist/expedition.css',
               '/assets/expedition/dist/expedition.iife.js',
           ]);

           if (!window.expedition || typeof window.expedition.mount !== 'function') {
               throw new Error('Expedition map SDK did not load.');
           }

           let embedStyle = document.getElementById('schedule-board-expedition-embed-style');
           if (!embedStyle) {
               embedStyle = document.createElement('style');
               embedStyle.id = 'schedule-board-expedition-embed-style';
               embedStyle.textContent = `
                   #expedition-board-map-host .expedition {
                       position: relative !important;
                       inset: auto !important;
                       width: 100% !important;
                       height: 100% !important;
                       min-height: 0 !important;
                   }
                   /* Keep Expedition's native legend/toggles useful without
                      allowing a long list of visit types to cover the map. */
                   #expedition-board-map-host .expedition__bc {
                       position: absolute !important;
                       left: var(--board-legend-left, 50%) !important;
                       right: auto !important;
                       top: var(--board-legend-top, auto) !important;
                       bottom: 14px !important;
                       transform: translateX(-50%) !important;
                       max-width: min(460px, calc(100% - 180px)) !important;
                   }
                   #expedition-board-map-host .expedition__bc.is-board-dragged {
                       bottom: auto !important;
                       transform: none !important;
                       cursor: grab;
                   }
                   #expedition-board-map-host .expedition__bc.is-board-dragged:active { cursor: grabbing; }
                   /* SearchBar is fixed in standalone Expedition.  The board
                      embeds Expedition in a panel, so it must be panel-bound. */
                   #expedition-board-map-host .sb {
                       position: absolute !important;
                       top: 12px !important;
                       left: 50% !important;
                       width: min(460px, calc(100% - 120px)) !important;
                       transform: translateX(-50%) !important;
                   }
                   #expedition-board-map-host .legend {
                       max-width: 100% !important;
                       max-height: 100px;
                       overflow-y: auto;
                       padding: 7px;
                       background: rgba(37, 55, 82, .94);
                       border: 1px solid rgba(255,255,255,.16);
                       border-radius: 14px;
                       box-shadow: 0 10px 28px rgba(15,23,42,.34);
                       scrollbar-width: thin;
                   }
                   #expedition-board-map-host .legend__chip {
                       font-size: 11px;
                       max-width: 195px;
                   }
                   #expedition-board-map-host .legend__chip--all {
                       order: -1;
                       background: rgba(59,130,246,.34);
                       font-weight: 700;
                   }
                   #expedition-board-map-host .legend__label {
                       max-width: 145px;
                   }
               `;
               document.head.appendChild(embedStyle);
           }

           host.textContent = '';
           const mapRoot = document.createElement('div');
           mapRoot.style.height = '100%';
           mapRoot.style.minHeight = '0';
           host.appendChild(mapRoot);
           const mapConfigResponse = await frappe.call({
               method: 'field_service_management.field_service_management.page.api.ensure_today_board_expedition_map',
           });
           const mapConfig = mapConfigResponse?.message || {};
           nativeTodayBoardLayers = (Array.isArray(mapConfig.layers) ? mapConfig.layers : [])
               .map(function (layer) {
                   return typeof layer === 'string'
                       ? { name: layer, title: layer }
                       : layer;
               })
               .filter(function (layer) { return layer && layer.name; });
           configuredMapVisitTypes = nativeTodayBoardLayers
               .map(function (layer) { return layer.visit_type; })
               .filter(Boolean);
           nativeTodayBoardLayerNames = nativeTodayBoardLayers.map(function (layer) {
               return layer.name;
           });
           const app = window.expedition.mount(mapRoot, {
               embedded: true,
               mapName: mapConfig.name || 'rerbv0jr65',
               mapTitle: mapConfig.title || 'BMS Field Service Dispatch',
           });
           if (!app) throw new Error('Expedition did not mount into the map panel.');
           host.dataset.expeditionMounted = '1';
           setupNativeLegendDrag(host);
       } catch (error) {
           console.error('Unable to load Expedition map:', error);
           host.textContent = 'Unable to load the Expedition map. Please check that the Expedition app is installed and built.';
       } finally {
           delete host.dataset.expeditionMountStarted;
       }
   }

   function renderRichTextForBoard(value) {
       const escape = function (text) {
           return String(text == null ? '' : text)
               .replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;')
               .replace(/"/g, '&quot;')
               .replace(/'/g, '&#39;');
       };
       const parser = new DOMParser();
       const source = parser.parseFromString(String(value == null ? '' : value), 'text/html').body;
       const allowedTags = new Set(['p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'ol', 'ul', 'li', 'div', 'span', 'blockquote', 'a']);
       const renderNode = function (node) {
           if (node.nodeType === Node.TEXT_NODE) return escape(node.nodeValue);
           if (node.nodeType !== Node.ELEMENT_NODE) return '';
           const tag = node.tagName.toLowerCase();
           const content = Array.from(node.childNodes).map(renderNode).join('');
           if (!allowedTags.has(tag)) return content;
           if (tag === 'a') {
               const href = String(node.getAttribute('href') || '').trim();
               return /^(https?:|mailto:)/i.test(href)
                   ? `<a href="${escape(href)}" target="_blank" rel="noopener">${content}</a>`
                   : content;
           }
           return tag === 'br' ? '<br>' : `<${tag}>${content}</${tag}>`;
       };
       return Array.from(source.childNodes).map(renderNode).join('');
   }

   function hydrateRichTextDescriptions() {
       document.querySelectorAll('.maintenance-description-value').forEach(function (node) {
           node.innerHTML = renderRichTextForBoard(node.textContent || '');
       });
   }

   frappe.call({
       method: "field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.get_context",
       callback: function (r) {
           if (r.message) {
               $(frappe.render_template("schedule_board_today", r.message, r.issues)).appendTo(page.body);
               hydrateTechnicianAvatars();
               hydrateRichTextDescriptions();
               applyVisitFilters();
               window.requestAnimationFrame(restoreVisitPanelHeight);
           } else {
               console.log("No message returned from the server.");
           }
       }
   });




   $(document).ready(function () {

       function getMapProtectedTop() {
           const toolbar = document.querySelector('.visit-list-toolbar');
           const toolbarBottom = toolbar ? toolbar.getBoundingClientRect().bottom + 12 : 76;
           return Math.max(76, Math.min(window.innerHeight - 12, Math.ceil(toolbarBottom)));
       }

       function clampMapTop(section, proposedTop) {
           const minimumTop = getMapProtectedTop();
           const maximumTop = Math.max(minimumTop, window.innerHeight - section.offsetHeight - 8);
           return Math.max(minimumTop, Math.min(maximumTop, proposedTop));
       }

       $(document).on('click', '#toggle-expedition-board-map', async function () {
           const section = document.getElementById('expedition-board-map-section');
           const workspace = document.getElementById('schedule-board-workspace');
           const resizer = document.getElementById('board-map-resizer');
           if (!section) return;
           setupMapPanelResizer();
           setupDraggableMapPanel();

           const button = this;
           const isOpening = section.hidden;
           section.hidden = !isOpening;
           workspace?.classList.toggle('is-map-open', isOpening);
           workspace?.classList.remove('is-map-floating');
           section.removeAttribute('style');
           if (isOpening && !window.matchMedia('(min-width: 1180px)').matches) {
               section.style.top = 'auto';
               section.style.bottom = '12px';
           }
           document.querySelectorAll('.board-map-floating-resize').forEach((handle) => {
               handle.hidden = !isOpening;
               handle.classList.remove('is-resizing');
           });
           if (resizer) {
               resizer.hidden = !isOpening || !window.matchMedia('(min-width: 1180px)').matches;
           }
           button.setAttribute('aria-expanded', String(isOpening));
           button.setAttribute('aria-label', isOpening ? 'Hide Expedition map' : 'Show Expedition map');
           button.setAttribute('title', isOpening ? 'Hide Expedition map' : 'Show Expedition map');

           if (isOpening) {
               try {
                   const savedWidth = Number(localStorage.getItem('schedule-board-today-map-panel-width'));
                   if (Number.isFinite(savedWidth) && savedWidth >= 380) {
                       const maxWidth = Math.min(900, (workspace?.clientWidth || window.innerWidth) - 568);
                       workspace?.style.setProperty('--board-map-width', Math.max(380, Math.min(maxWidth, savedWidth)) + 'px');
                   }
               } catch (error) {
                   // Use the default panel width when browser storage is disabled.
               }
               await mountExpeditionBoardMap();
               refreshMapMaintenanceVisits();
               startLiveTechnicianLocations();
           } else {
               stopLiveTechnicianLocations();
           }
       });

       $(document).on('click', '#close-expedition-board-map', function () {
           $('#toggle-expedition-board-map').trigger('click');
       });

       $(document).on('click', '.map-date-range-button', function () {
           selectedMapDateRange = String(this.dataset.mapRange || 'today');
           $('.map-date-range-button').attr('aria-pressed', 'false');
           $(this).attr('aria-pressed', 'true');
           const summary = document.getElementById('map-date-range-summary');
           if (summary) summary.textContent = `Loading ${getMapDateRange(selectedMapDateRange).label.toLowerCase()} route plan...`;
           refreshMapMaintenanceVisits();
       });

       $(document).on('input', '#map-technician-search', function () {
           if (this.value.trim().length < 2) {
               this.removeAttribute('aria-invalid');
               return;
           }
           locateMapTechnician(false);
       });

       $(document).on('submit', '#map-technician-search-form', function (event) {
           event.preventDefault();
           locateMapTechnician(true);
       });

       $(document).on('click', '.map-technician-layer-filter', function () {
           techniciansVisibleOnMap = !techniciansVisibleOnMap;
           const map = window.expeditionMap?.getMap?.();
           if (map) renderLiveTechnicianDomMarkers(map, liveTechnicianFeatures);
           renderMapVisitTypeFilters(mapVisitFeatures);
       });

       $(document).on('click', '.map-visit-type-filter', function () {
           const visitType = this.dataset.visitType;
           if (!visitType) return;
           if (hiddenMapVisitTypes.has(visitType)) {
               hiddenMapVisitTypes.delete(visitType);
           } else {
               hiddenMapVisitTypes.add(visitType);
           }
           const map = window.expeditionMap?.getMap?.();
           if (map) renderMapVisitDomMarkers(map, mapVisitFeatures);
           renderMapVisitTypeFilters(mapVisitFeatures);
       });

       function setupMapPanelResizer() {
           const workspace = document.getElementById('schedule-board-workspace');
           const handle = document.getElementById('board-map-resizer');
           if (!workspace || !handle) return;
           if (handle.dataset.resizerInitialized === '1') return;
           handle.dataset.resizerInitialized = '1';

           let activePointerId = null;
           const resizeMapPanel = function (event) {
               if (activePointerId !== event.pointerId) return;
               const bounds = workspace.getBoundingClientRect();
               const maxWidth = Math.min(900, bounds.width - 568);
               const width = Math.round(Math.max(380, Math.min(maxWidth, bounds.right - event.clientX)));
               workspace.style.setProperty('--board-map-width', width + 'px');
               handle.setAttribute('aria-valuenow', String(width));
           };
           handle.addEventListener('pointerdown', function (event) {
               if (!workspace.classList.contains('is-map-open') || handle.hidden) return;
               activePointerId = event.pointerId;
               handle.classList.add('is-resizing');
               handle.setPointerCapture(event.pointerId);
               document.body.style.cursor = 'col-resize';
               document.body.style.userSelect = 'none';
               event.preventDefault();
           });
           handle.addEventListener('pointermove', resizeMapPanel);
           const stopResize = function (event) {
               if (activePointerId !== event.pointerId) return;
               try {
                   const currentWidth = parseInt(getComputedStyle(workspace).getPropertyValue('--board-map-width'), 10);
                   if (Number.isFinite(currentWidth)) {
                       localStorage.setItem('schedule-board-today-map-panel-width', String(currentWidth));
                   }
               } catch (error) {
                   // Resizing still works when browser storage is disabled.
               }
               activePointerId = null;
               handle.classList.remove('is-resizing');
               document.body.style.cursor = '';
               document.body.style.userSelect = '';
           };
           handle.addEventListener('pointerup', stopResize);
           handle.addEventListener('pointercancel', stopResize);
           handle.addEventListener('keydown', function (event) {
               if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
               event.preventDefault();
               const currentWidth = parseInt(getComputedStyle(workspace).getPropertyValue('--board-map-width'), 10) || Math.round(workspace.clientWidth * 0.4);
               const direction = event.key === 'ArrowLeft' ? 1 : -1;
               const maxWidth = Math.min(900, workspace.clientWidth - 568);
               const width = Math.max(380, Math.min(maxWidth, currentWidth + direction * 24));
               workspace.style.setProperty('--board-map-width', width + 'px');
               handle.setAttribute('aria-valuenow', String(width));
           });
       }

       function setupDraggableMapPanel() {
           const workspace = document.getElementById('schedule-board-workspace');
           const section = document.getElementById('expedition-board-map-section');
           const header = section?.querySelector('.expedition-board-map-header');
           const moveHandle = document.getElementById('board-map-floating-move');
           if (!workspace || !section || !header || !moveHandle) return;
           if (section.dataset.dragHandlersInitialized === '1') return;
           section.dataset.dragHandlersInitialized = '1';

           let dragPointerId = null;
           let dragOrigin = null;
           const startDragging = function (event) {
               if (event.button !== 0 || event.target.closest('button, input, form, label')) return;
               const rect = section.getBoundingClientRect();
               let width = rect.width;
               let height = rect.height;
               try {
                   const savedSize = JSON.parse(localStorage.getItem('schedule-board-today-map-floating-size') || '{}');
                   if (Number.isFinite(savedSize.width)) width = Math.max(320, Math.min(window.innerWidth - 24, savedSize.width));
                   if (Number.isFinite(savedSize.height)) height = Math.max(260, Math.min(window.innerHeight - rect.top - 12, savedSize.height));
               } catch (error) {
                   // Use the current panel size when browser storage is disabled.
               }
               workspace.classList.add('is-map-floating');
               const protectedTop = getMapProtectedTop();
               height = Math.max(260, Math.min(height, window.innerHeight - protectedTop - 12));
               const initialLeft = Math.max(0, rect.right - width);
               const initialTop = clampMapTop(section, rect.top);
               section.style.left = initialLeft + 'px';
               section.style.top = initialTop + 'px';
               section.style.right = 'auto';
               section.style.bottom = 'auto';
               section.style.width = width + 'px';
               section.style.height = height + 'px';
               document.querySelectorAll('.board-map-floating-resize').forEach((handle) => { handle.hidden = false; });
               dragPointerId = event.pointerId;
               dragOrigin = { x: event.clientX, y: event.clientY, left: initialLeft, top: initialTop };
               event.currentTarget.setPointerCapture(event.pointerId);
               document.body.style.cursor = 'grabbing';
               document.body.style.userSelect = 'none';
               event.preventDefault();
           };
           const movePanel = function (event) {
               if (dragPointerId !== event.pointerId || !dragOrigin) return;
               const maxLeft = Math.max(0, window.innerWidth - section.offsetWidth);
               section.style.left = Math.max(0, Math.min(maxLeft, dragOrigin.left + event.clientX - dragOrigin.x)) + 'px';
               section.style.top = clampMapTop(section, dragOrigin.top + event.clientY - dragOrigin.y) + 'px';
           };
           const stopDragging = function (event) {
               if (dragPointerId !== event.pointerId) return;
               dragPointerId = null;
               dragOrigin = null;
               document.body.style.cursor = '';
               document.body.style.userSelect = '';
           };
           [header, moveHandle].forEach((dragHandle) => {
               dragHandle.addEventListener('pointerdown', startDragging);
               dragHandle.addEventListener('pointermove', movePanel);
               dragHandle.addEventListener('pointerup', stopDragging);
               dragHandle.addEventListener('pointercancel', stopDragging);
           });
           moveHandle.addEventListener('keydown', function (event) {
               if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
               event.preventDefault();
               if (!workspace.classList.contains('is-map-floating')) {
                   const rect = section.getBoundingClientRect();
                   workspace.classList.add('is-map-floating');
                   section.style.left = rect.left + 'px';
                   section.style.top = rect.top + 'px';
                   section.style.right = 'auto';
                   section.style.bottom = 'auto';
                   section.style.width = rect.width + 'px';
                   section.style.height = rect.height + 'px';
                   document.querySelectorAll('.board-map-floating-resize').forEach((handle) => { handle.hidden = false; });
               }
               const step = event.shiftKey ? 40 : 16;
               const left = parseFloat(section.style.left) || 0;
               const top = parseFloat(section.style.top) || 0;
               section.style.left = Math.max(0, Math.min(window.innerWidth - section.offsetWidth,
                   left + (event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0))) + 'px';
               section.style.top = clampMapTop(section,
                   top + (event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0)) + 'px';
           });

           const beginResize = function (handle, mode) {
               let pointerId = null;
               let origin = null;
               handle.addEventListener('pointerdown', function (event) {
                   if (section.hidden || handle.hidden || event.button !== 0) return;
                   const rect = section.getBoundingClientRect();
                   pointerId = event.pointerId;
                   origin = { x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, width: rect.width, height: rect.height };
                   handle.classList.add('is-resizing');
                   handle.setPointerCapture(event.pointerId);
                   document.body.style.cursor = mode === 'width' ? 'ew-resize' : mode === 'height' ? 'ns-resize' : 'nwse-resize';
                   document.body.style.userSelect = 'none';
                   event.preventDefault();
               });
               handle.addEventListener('pointermove', function (event) {
                   if (pointerId !== event.pointerId || !origin) return;
                   const floating = workspace.classList.contains('is-map-floating');
                   const deltaX = event.clientX - origin.x;
                   const deltaY = event.clientY - origin.y;
                   if (mode !== 'height') {
                       const minWidth = Math.min(320, window.innerWidth - 24);
                       const maxWidth = Math.max(minWidth, window.innerWidth - 24);
                       const width = Math.max(minWidth, Math.min(maxWidth, mode === 'width' ? origin.width - deltaX : origin.width + deltaX));
                       section.style.width = Math.round(width) + 'px';
                       if (floating && mode === 'width') {
                           section.style.left = Math.max(0, Math.min(window.innerWidth - width, origin.left + origin.width - width)) + 'px';
                       }
                   }
                   if (mode !== 'width') {
                       const minHeight = 260;
                       const height = Math.max(minHeight, Math.min(window.innerHeight - origin.top - 12, mode === 'height' ? origin.height + deltaY : origin.height + deltaY));
                       section.style.height = Math.round(height) + 'px';
                       section.style.bottom = 'auto';
                   }
               });
               const finishResize = function (event) {
                   if (pointerId !== event.pointerId) return;
                   pointerId = null;
                   origin = null;
                   handle.classList.remove('is-resizing');
                   document.body.style.cursor = '';
                   document.body.style.userSelect = '';
                   try {
                       localStorage.setItem('schedule-board-today-map-floating-size', JSON.stringify({
                           width: Math.round(section.getBoundingClientRect().width),
                           height: Math.round(section.getBoundingClientRect().height),
                       }));
                   } catch (error) {
                       // Resizing remains available when browser storage is disabled.
                   }
               };
               handle.addEventListener('pointerup', finishResize);
               handle.addEventListener('pointercancel', finishResize);
           };

           beginResize(document.getElementById('board-map-floating-resize-x'), 'width');
           beginResize(document.getElementById('board-map-floating-resize-y'), 'height');
           beginResize(document.getElementById('board-map-floating-resize-corner'), 'corner');
       }


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


       $(document).on('input', '#visit-search-filter, #customer-search-filter', applyVisitFilters);
       $(document).on('change', '#visit-status-filter, #visit-type-filter, #visit-territory-filter', function () {
           loadVisitQueueAssignment('unassigned');
       });
       $(document).on('change', '#visit-assignment-filter', function () {
           loadVisitQueueAssignment(String($(this).val() || 'unassigned'));
       });
       $(document).on('click', '#clear-visit-filters', function () {
           $('#visit-search-filter, #customer-search-filter, #visit-status-filter, #visit-type-filter, #visit-territory-filter').val('');
           $('#visit-assignment-filter').val('unassigned');
           loadVisitQueueAssignment('unassigned');
           $('#visit-search-filter').trigger('focus');
       });


       $(document).on('change', '#calendar-technician-filter', function () {
           const selectedTechnician = normalizeVisitFilterValue($(this).val());
           $('.calendar-technician-entry').each(function () {
               const entryTechnician = normalizeVisitFilterValue($(this).attr('data-technician'));
               const shouldHide = selectedTechnician && entryTechnician !== selectedTechnician;
               // OLD: $(this).toggleClass('d-none', shouldHide);
               // `d-flex` can override `d-none`; use the board-specific class
               // so the technician label and timeline are always hidden together.
               $(this).toggleClass('calendar-technician-hidden', Boolean(shouldHide));
           });
       });

       function closeTechnicianDayVisits() {
           $('#technician-day-visit-panel').prop('hidden', true);
           $('#technician-panel-resizer').prop('hidden', true);
           $('.calendar-section').removeClass('technician-visits-open');
           $('.calendar-technician-select').attr('aria-expanded', 'false').removeClass('calendar-technician-selected');
       }

       function setTechnicianPanelWidth(width, section) {
           const bounds = section.getBoundingClientRect();
           const minimumPanelWidth = 280;
           const maximumPanelWidth = Math.min(600, bounds.width - 520);
           if (maximumPanelWidth < minimumPanelWidth) return;

           const safeWidth = Math.max(minimumPanelWidth, Math.min(maximumPanelWidth, width));
           section.style.setProperty('--technician-panel-width', safeWidth + 'px');
           const resizer = $('#technician-panel-resizer');
           resizer.attr('aria-valuemin', minimumPanelWidth);
           resizer.attr('aria-valuemax', Math.round(maximumPanelWidth));
           resizer.attr('aria-valuenow', Math.round(safeWidth));
           try {
               localStorage.setItem('schedule-board-today-technician-panel-width', String(Math.round(safeWidth)));
           } catch (error) {
               // Keep resizing available when browser storage is disabled.
           }
       }

       function restoreTechnicianPanelWidth(section) {
           let storedWidth = 330;
           try {
               const savedWidth = Number(localStorage.getItem('schedule-board-today-technician-panel-width'));
               if (Number.isFinite(savedWidth) && savedWidth > 0) storedWidth = savedWidth;
           } catch (error) {
               // Use the default width when browser storage is disabled.
           }
           setTechnicianPanelWidth(storedWidth, section);
       }

       function renderTechnicianDayVisits(technician, visits) {
           const list = $('#technician-day-visit-list').empty();
           $('#technician-day-visit-title').text(technician + ' - Today schedule');

           if (!visits || !visits.length) {
               list.append($('<div class="text-muted">').text('No scheduled visits for this technician today.'));
               return;
           }

           visits.forEach(function (visit, index) {
               const card = $('<article class="technician-day-visit-card">');
               card.append($('<span class="technician-day-visit-number">').text(index + 1));
               const content = $('<div class="technician-day-visit-content">');
               const link = $('<a>').attr('href', '/app/maintenance-visit/' + encodeURIComponent(visit.name)).text(visit.name);
               content.append($('<div>').append(link));
               const meta = $('<div class="technician-day-visit-meta">');
               const metaParts = [];
               if (visit.maintenance_type) metaParts.push($('<span>').text(visit.maintenance_type));
               if (visit.customer) {
                   const customer = visit.customer_link
                       ? $('<a>').attr('href', '/app/customer/' + encodeURIComponent(visit.customer_link))
                           .attr('target', '_blank').attr('rel', 'noopener').text(visit.customer)
                       : $('<span>').text(visit.customer);
                   metaParts.push(customer);
               }
               const visitStatus = visit.completion_status || visit.status;
               if (visitStatus) metaParts.push($('<span>').text(visitStatus));
               metaParts.forEach(function (part, index) {
                   if (index) meta.append(document.createTextNode(' · '));
                   meta.append(part);
               });
               content.append(meta);
               const time = [visit.start_time, visit.end_time].filter(Boolean).join(' – ');
               if (time) {
                   content.append($('<div class="technician-day-visit-meta">').text(time));
               }
               if (visit.address) {
                   const address = String(visit.address)
                       .replace(/<br\s*\/?>/gi, '\n')
                       .replace(/&lt;br\s*\/?>/gi, '\n')
                       .replace(/\r\n?/g, '\n');
                   content.append($('<div class="technician-day-visit-meta technician-day-visit-address">').text(address));
               }
               card.append(content);
               list.append(card);
           });
       }

       function openTechnicianDayVisits(technician) {
           const panel = $('#technician-day-visit-panel');
           panel.prop('hidden', false);
           const calendarSection = $('.calendar-section').addClass('technician-visits-open').get(0);
           $('#technician-panel-resizer').prop('hidden', false);
           restoreTechnicianPanelWidth(calendarSection);
           $('#technician-day-visit-title').text(technician + ' - Today schedule');
           $('#technician-day-visit-list').empty().append(
               $('<div class="text-muted">').text('Loading today schedule...')
           );
           $('.calendar-technician-select').attr('aria-expanded', 'false').removeClass('calendar-technician-selected');
           $('.calendar-technician-select').filter(function () {
               return $(this).attr('data-technician') === technician;
           }).attr('aria-expanded', 'true').addClass('calendar-technician-selected');

           frappe.call({
               method: 'field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.get_technician_day_visits',
               args: { technician: technician },
               callback: function (response) {
                   if (response.message) {
                       renderTechnicianDayVisits(technician, response.message);
                   } else {
                       $('#technician-day-visit-list').empty().append(
                           $('<div class="text-muted">').text('Unable to load the technician schedule.')
                       );
                   }
               },
               error: function () {
                   $('#technician-day-visit-list').empty().append(
                       $('<div class="text-muted">').text('Unable to load the technician schedule.')
                   );
               }
           });
       }

       $(document).on('click', '.calendar-technician-select', function (event) {
           if ($(event.target).closest('a, button').length) return;
           openTechnicianDayVisits($(this).attr('data-technician'));
       });

       $(document).on('keydown', '.calendar-technician-select', function (event) {
           if (event.key === 'Enter' || event.key === ' ') {
               event.preventDefault();
               openTechnicianDayVisits($(this).attr('data-technician'));
           }
       });

       $(document).on('click', '#close-technician-day-visits', closeTechnicianDayVisits);

       $(document).on('pointerdown', '#visit-calendar-resizer', function (event) {
           if (window.matchMedia('(max-width: 1100px)').matches) return;
           event.preventDefault();
           const resizer = event.currentTarget;
           const stack = $('.board-sections-stack').get(0);
           if (!stack) return;

           resizer.classList.add('is-resizing');
           const pointerId = event.originalEvent ? event.originalEvent.pointerId : event.pointerId;
           if (resizer.setPointerCapture && pointerId !== undefined) resizer.setPointerCapture(pointerId);
           const resizeVisits = function (moveEvent) {
               setVisitPanelHeight(moveEvent.clientY - stack.getBoundingClientRect().top);
           };
           const finishResize = function () {
               resizer.classList.remove('is-resizing');
               resizer.removeEventListener('pointermove', resizeVisits);
               resizer.removeEventListener('pointerup', finishResize);
               resizer.removeEventListener('pointercancel', finishResize);
           };
           resizer.addEventListener('pointermove', resizeVisits);
           resizer.addEventListener('pointerup', finishResize);
           resizer.addEventListener('pointercancel', finishResize);
       });

       $(document).on('keydown', '#visit-calendar-resizer', function (event) {
           if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown' && event.key !== 'Home' && event.key !== 'End') return;
           event.preventDefault();
           const currentHeight = $('.visits-panel').outerHeight();
           const step = event.shiftKey ? 60 : 24;
           const nextHeight = event.key === 'Home' ? 190
               : event.key === 'End' ? 480
               : currentHeight + (event.key === 'ArrowUp' ? step : -step);
           setVisitPanelHeight(nextHeight);
       });

       $(document).on('pointerdown', '#technician-panel-resizer', function (event) {
           if (window.matchMedia('(max-width: 1100px)').matches) return;
           event.preventDefault();
           const resizer = event.currentTarget;
           const section = $('.calendar-section').get(0);
           if (!section || $('#technician-day-visit-panel').prop('hidden')) return;

           resizer.classList.add('is-resizing');
           const pointerId = event.originalEvent ? event.originalEvent.pointerId : event.pointerId;
           if (resizer.setPointerCapture && pointerId !== undefined) resizer.setPointerCapture(pointerId);
           const resizePanel = function (moveEvent) {
               const sectionRight = section.getBoundingClientRect().right;
               setTechnicianPanelWidth(sectionRight - moveEvent.clientX, section);
           };
           const finishResize = function () {
               resizer.classList.remove('is-resizing');
               resizer.removeEventListener('pointermove', resizePanel);
               resizer.removeEventListener('pointerup', finishResize);
               resizer.removeEventListener('pointercancel', finishResize);
           };
           resizer.addEventListener('pointermove', resizePanel);
           resizer.addEventListener('pointerup', finishResize);
           resizer.addEventListener('pointercancel', finishResize);
       });

       $(document).on('keydown', '#technician-panel-resizer', function (event) {
           if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight' && event.key !== 'Home' && event.key !== 'End') return;
           event.preventDefault();
           const section = $('.calendar-section').get(0);
           const currentWidth = $('#technician-day-visit-panel').outerWidth();
           const step = event.shiftKey ? 60 : 24;
           const nextWidth = event.key === 'Home' ? 280
               : event.key === 'End' ? 600
               : currentWidth + (event.key === 'ArrowLeft' ? step : -step);
           setTechnicianPanelWidth(nextWidth, section);
       });






       $(document).on("click", ".submit", function () {
           const issueId = $(this).data("issue");
           const form = $("#custom-form-" + issueId);


           if (!form.find(".etime").val()) {
               alert("Please select an end time.");
               return;
           }


           // Collect form data
           const formData = {
               code: form.find(".code").val(),
               technicians: form.find(".technician").val(),
               date: form.find(".date").val(),
               stime: form.find(".stime").val(),
               etime: form.find(".etime").val()
           };


           // Make an API call to Frappe to save the data in your Doctype
           frappe.call({
               method: "field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.save_form_data",
               args: {
                   form_data: formData
               },
               callback: function (response) {
                   if (response.message.success) {
                       alert("Maintenance Visit scheduled successfully!");
                       window.location.reload();
                   } else {
                       alert(`Form submission failed!" ${response.message.message}`);
                   }
               },
               error: function (error) {
                   console.error(error);
                   alert("An error occurred while submitting the form!");
               }
           });
       });






       let liveMap = null;
       let liveMapMaintenance = [];
       let liveMapMaintenanceLoaded = false;
       let liveMapPreloadData = null;
       let liveMapPreloadStarted = false;
       let updateInterval = null;


       function formatTechnicianTime(value) {
           return value ? String(value).split('.')[0] : '';
       }




       function preloadLiveLocations() {
           if (liveMapPreloadStarted || liveMapPreloadData) {
               return;
           }
           liveMapPreloadStarted = true;
           frappe.call({
               method: "field_service_management.field_service_management.page.api.get_live_locations",
               callback: function (r) {
                   if (r.message) {
                       liveMapPreloadData = r.message;
                   }
                   liveMapPreloadStarted = false;
               },
               error: function () {
                   liveMapPreloadStarted = false;
               }
           });
       }


       // OLD MAP PRELOAD: Expedition now owns the Today board map data.
       // preloadLiveLocations();


       /* OLD PER-VISIT DETAIL MODAL HANDLER
       $(document).on('click', 'a[data-id]', function () {
           const modalId = $(this).data('id'); // Get the modal ID
           const openedModal = $(`#${modalId}`);
           openedModal.removeClass('hide').addClass('show'); // Toggle classes
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
                   method: "field_service_management.field_service_management.page.api.get_cords",
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
                               iconUrl: '/files/technician.png',
                               iconSize: [25, 41],
                               iconAnchor: [12, 41],
                               popupAnchor: [1, -34]
                           });


                           technicians.forEach(tech => {
                               L.marker([tech.latitude, tech.longitude], { icon: greenIcon }).addTo(map)
                                   .bindPopup(`
                                       <div style="font-family:Inter,Arial,sans-serif;line-height:1.4;">
                                           <strong>${tech.technician_name}</strong><br>
                                           <span style="color:#6B7280;font-size:12px;">
                                               ${tech.technician}
                                           </span><br><br>
                                           <span style="font-size:12px;">
                                               📍 ${Number(tech.latitude).toFixed(4)}, ${Number(tech.longitude).toFixed(4)}
                                           </span><br>
                                           <span style="font-size:12px;">
                                               🕒 ${formatTechnicianTime(tech.time)}
                                           </span>
                                       </div>
                                   `);
                           });
                       } else {
                           console.log("No cords returned from the server.");
                       }
                   }
               });
           }
       });
       END OLD PER-VISIT DETAIL MODAL HANDLER */


       // Calendar tasks still use their scheduling modal. Keep this handler
       // separate from the disabled legacy Maintenance Visit detail handler.
       function normalizeCalendarTimeInput(value) {
           const match = String(value || '').match(/(\d{1,2}):(\d{2})/);
           if (!match) return '';
           return String(Number(match[1])).padStart(2, '0') + ':' + match[2];
       }

       function normalizeCalendarTaskTimeFields(taskModal) {
           taskModal.find('.stime, .etime').each(function () {
               const field = $(this);
               const normalized = normalizeCalendarTimeInput(field.val() || field.attr('value'));
               if (normalized) field.val(normalized).attr('value', normalized);
           });
       }

       function openCalendarTaskModal(taskCard) {
           const modalId = taskCard.attr('data-modal-id');
           if (!modalId) {
               return;
           }

           setBoardVisitSelection(taskCard.attr('data-issue'));

           const taskModal = $('#' + modalId);
           if (!taskModal.length) {
               console.error('Calendar task modal was not found:', modalId);
               return;
           }

           normalizeCalendarTaskTimeFields(taskModal);
           taskModal.removeClass('hide').addClass('show');
           $('body').addClass('calendar-task-modal-open');
       }


       function closeCalendarTaskModal(taskModal) {
           taskModal.removeClass('show').addClass('hide');
           if (!$('.calendar-task-modal.show').length) {
               $('body').removeClass('calendar-task-modal-open');
           }
       }


       $(document).on('click', '.calendar-task-card', function (event) {
           event.preventDefault();
           openCalendarTaskModal($(this));
       });


       $(document).on('keydown', '.calendar-task-card', function (event) {
           if (event.key !== 'Enter' && event.key !== ' ') {
               return;
           }
           event.preventDefault();
           openCalendarTaskModal($(this));
       });


       $(document).on('click', '.calendar-task-modal', function (event) {
           if (event.target === this) {
               closeCalendarTaskModal($(this));
           }
       });


       $(document).on('keydown', function (event) {
           if (event.key === 'Escape' && $('.calendar-task-modal.show').length) {
               closeCalendarTaskModal($('.calendar-task-modal.show').last());
           }
       });


       const maintenanceVisitDetailsCache = new Map();

       function setBoardVisitSelection(issueId) {
           $('.maintenance-visit-card, .calendar-task-card').removeClass('is-selected');
           if (!issueId) return;

           $('.maintenance-visit-card, .calendar-task-card').filter(function () {
               return String($(this).attr('data-issue') || '') === String(issueId);
            }).addClass('is-selected');
           focusExpeditionVisit(issueId);
       }

       function focusExpeditionVisit(issueId) {
           const mapApi = window.expeditionMap;
           const expeditionApi = window.Expedition;
           if (!mapApi || typeof mapApi.getLayerDiagnostics !== 'function' ||
               typeof mapApi.flyTo !== 'function' || typeof expeditionApi?.getLayerFeatures !== 'function') {
               return;
           }

           const matchingKeys = ['maintenance_visit', 'visit_name', 'name'];
           const layers = mapApi.getLayerDiagnostics() || [];
           for (const layer of layers) {
               const features = expeditionApi.getLayerFeatures(layer.name) || [];
               const match = features.find((feature) => {
                   const properties = feature && feature.properties ? feature.properties : {};
                   const doctype = properties._doctype || properties.doctype || '';
                   if (doctype && doctype !== 'Maintenance Visit') return false;
                   return matchingKeys.some((key) => String(properties[key] || '') === String(issueId));
               });
               const coordinates = match && match.geometry && match.geometry.coordinates;
               if (Array.isArray(coordinates) && coordinates.length >= 2 &&
                   Number.isFinite(Number(coordinates[0])) && Number.isFinite(Number(coordinates[1]))) {
                   mapApi.flyTo({
                       center: [Number(coordinates[0]), Number(coordinates[1])],
                       zoom: Math.max(Number(mapApi.getZoom && mapApi.getZoom()) || 0, 15),
                       duration: 650,
                   });
                   return;
               }
           }
       }

       function selectBoardVisitFromMap(feature) {
           const properties = feature && feature.properties ? feature.properties : {};
           const doctype = properties._doctype || properties.doctype || '';
           const issueId = properties.maintenance_visit || properties.visit_name ||
               ((doctype === 'Maintenance Visit' || !doctype) ? properties.name : null);
           if (!issueId) return;

           const matchingVisit = $('.maintenance-visit-card, .calendar-task-card').filter(function () {
               return String($(this).attr('data-issue') || '') === String(issueId);
           }).length;
           if (matchingVisit) setBoardVisitSelection(issueId);
       }

       window.addEventListener('expedition:feature-selected', function (event) {
           selectBoardVisitFromMap(event.detail && event.detail.feature);
       });
       window.addEventListener('expedition:feature-deselected', function () {
           setBoardVisitSelection(null);
       });

       function escapeDetailsHtml(value) {
           return String(value == null ? '' : value)
               .replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;')
               .replace(/"/g, '&quot;')
               .replace(/'/g, '&#39;');
       }

       function renderRichText(value) {
           const raw = String(value == null ? '' : value).trim();
           if (!raw) return '';
           const parser = new DOMParser();
           const source = parser.parseFromString(raw, 'text/html').body;
           const allowedTags = new Set(['p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'ol', 'ul', 'li', 'div', 'span', 'blockquote', 'a']);
           const renderNode = (node) => {
               if (node.nodeType === Node.TEXT_NODE) return escapeDetailsHtml(node.nodeValue);
               if (node.nodeType !== Node.ELEMENT_NODE) return '';
               const tag = node.tagName.toLowerCase();
               const content = Array.from(node.childNodes).map(renderNode).join('');
               if (!allowedTags.has(tag)) return content;
               if (tag === 'a') {
                   const href = String(node.getAttribute('href') || '').trim();
                   if (/^(https?:|mailto:)/i.test(href)) {
                       return `<a href="${escapeDetailsHtml(href)}" target="_blank" rel="noopener">${content}</a>`;
                   }
                   return content;
               }
               if (tag === 'br') return '<br>';
               return `<${tag}>${content}</${tag}>`;
           };
           return Array.from(source.childNodes).map(renderNode).join('');
       }

       function hydrateRichTextDescriptions() {
           document.querySelectorAll('.maintenance-description-value').forEach((node) => {
               const raw = node.textContent || '';
               node.innerHTML = renderRichText(raw);
           });
       }

       function visitMasterLink(doctype, value, label) {
           if (!value) return escapeDetailsHtml(label || 'Not specified');
           const path = '/app/' + doctype + '/' + encodeURIComponent(value);
           return `<a href="${escapeDetailsHtml(path)}" target="_blank" rel="noopener">${escapeDetailsHtml(label || value)}</a>`;
       }

       function detailField(label, value, options = {}) {
           let content = escapeDetailsHtml(value || options.empty || 'Not specified');
           if (value && options.link) content = visitMasterLink(options.link, value);
           if (options.email && value) content = `<a href="mailto:${escapeDetailsHtml(value)}">${escapeDetailsHtml(value)}</a>`;
           return `<div class="maintenance-detail-field"><span class="maintenance-detail-field-label">${escapeDetailsHtml(label)}</span><span class="maintenance-detail-field-value">${content}</span></div>`;
       }

       function emptyDetail(message) {
           return `<div class="maintenance-inline-empty">${escapeDetailsHtml(message)}</div>`;
       }

       function renderChecklistDetails(data) {
           const rows = data.checklist || [];
           if (!rows.length) return emptyDetail('No checklist is available for this Maintenance Visit.');
           const groups = new Map();
           rows.forEach((row) => {
               const key = row.item_code || '';
               if (!groups.has(key)) groups.set(key, []);
               groups.get(key).push(row);
           });

           let stepIndex = 0;
           const statusBadge = (complete) => `<span class="checklist-status-badge ${complete ? 'is-complete' : 'is-pending'}">${complete ? 'Completed' : 'Pending'}</span>`;
           const imageButton = (url, label) => url
               ? `<button type="button" class="checklist-preview-image-button" data-image="${escapeDetailsHtml(url)}">${escapeDetailsHtml(label || 'View image')}</button>`
               : '';
           const subStepLabel = (step) => {
               if (!step || typeof step !== 'object') return String(step || 'Sub-step');
               const keys = ['sub_step', 'sub_step_description', 'sub_step_text', 'sub_step_label', 'description', 'heading', 'activity', 'title', 'subject', 'step', 'step_name', 'name', 'sub_step_name'];
               const match = keys.find((key) => step[key]);
               return match ? step[match] : 'Sub-step';
           };
           const parseSubSteps = (raw) => {
               if (!raw) return [];
               try {
                   const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
                   if (Array.isArray(parsed)) return parsed;
                   if (parsed && typeof parsed === 'object') {
                       for (const key of ['sub_steps', 'steps', 'data']) {
                           if (Array.isArray(parsed[key])) return parsed[key];
                       }
                   }
               } catch (error) {
                   console.warn('Unable to parse checklist sub-steps', error);
               }
               return [];
           };
           const logs = data.sub_step_work_logs || [];
           const renderStep = (row) => {
               stepIndex += 1;
               const bodyId = `visit-checklist-step-${stepIndex}`;
               const complete = String(row.work_done || '').toLowerCase() === 'yes';
               const serial = row.serial_no ? visitMasterLink('serial-no', row.serial_no) : 'Not specified';
               let subSteps = parseSubSteps(row.sub_steps_json);
               if (!subSteps.length) subSteps = parseSubSteps(row.sub_steps_format_for_mobile_apk);
               const renderedSubSteps = subSteps.map((rawStep) => {
                   const step = rawStep && typeof rawStep === 'object' ? rawStep : { name: rawStep };
                   const stepNames = [step.name, step.sub_step_name, step.sub_step_original_name].filter(Boolean).map(String);
                   let log = logs.find((candidate) =>
                       candidate.parent_checklist_row === row.name &&
                       [candidate.sub_step_name, candidate.sub_step_original_name].filter(Boolean).some((name) => stepNames.includes(String(name)))
                   );
                   if (!log && row.idx && step.idx) {
                       log = logs.find((candidate) => candidate.parent_checklist_row === row.name && Number(candidate.idx) === Number(step.idx));
                   }
                   const workStatus = log && log.work_done ? log.work_done : (step.work_done || step.completed || step.is_completed || step.status);
                   const subComplete = ['yes', 'true', '1', 'completed', 'fully completed'].includes(String(workStatus || '').trim().toLowerCase());
                   const doneBy = (log && log.done_by) || step.done_by || 'Not completed';
                   const remark = (log && log.remark) || step.remark || '';
                   const image = (log && log.attachment) || step.image || step.attachment;
                   return `<div class="checklist-preview-substep"><div class="checklist-preview-substep-main"><span>${escapeDetailsHtml(subStepLabel(step))}</span>${statusBadge(subComplete)}</div><div class="checklist-preview-substep-meta"><span><strong>Done By:</strong> ${escapeDetailsHtml(doneBy)}</span>${remark ? `<span><strong>Remark:</strong> ${escapeDetailsHtml(remark)}</span>` : ''}${imageButton(image, 'View image')}</div></div>`;
               }).join('');
               const details = row.details ? `<div class="checklist-preview-details"><strong>Task List:</strong><div>${escapeDetailsHtml(row.details)}</div></div>` : '';
               const subStepContent = renderedSubSteps || emptyDetail('No sub-steps are available for this checklist item.');
               const parentImage = row.attachment || row.checklist_image;
               return `<article class="checklist-preview-step-card"><button type="button" class="checklist-preview-step-toggle" aria-expanded="false" aria-controls="${bodyId}"><span class="checklist-preview-chevron" aria-hidden="true">&#9656;</span><span class="checklist-preview-step-heading">${escapeDetailsHtml(row.heading || 'Checklist item')}</span>${statusBadge(complete)}</button><div class="checklist-preview-step-body" id="${bodyId}" hidden><div class="checklist-preview-metadata"><span><strong>Serial No:</strong> ${serial}</span><span><strong>Periodicity:</strong> ${escapeDetailsHtml(row.periodicity || 'Not specified')}</span><span><strong>Location:</strong> ${escapeDetailsHtml(row.item_location || 'Not specified')}</span><span><strong>Done By:</strong> ${escapeDetailsHtml(row.done_by || 'Not completed')}</span></div>${details}<div class="checklist-preview-parent-footer"><span><strong>Remark:</strong> ${escapeDetailsHtml(row.remark || 'No remark')}</span>${imageButton(parentImage, 'View checklist image')}</div><div class="checklist-preview-substeps"><div class="checklist-preview-substeps-title">Sub-steps</div>${subStepContent}</div></div></article>`;
           };
           return Array.from(groups.entries()).map(([itemCode, groupRows]) => {
               const itemName = groupRows[0].item_name || '';
               return `<section class="checklist-preview-group"><h6 class="checklist-preview-title">${itemCode ? visitMasterLink('item', itemCode) : 'Not specified'}${itemName ? `: ${escapeDetailsHtml(itemName)}` : ''}</h6>${groupRows.map(renderStep).join('')}</section>`;
           }).join('');
       }

       function renderMaintenanceVisitDetails(data) {
           const visit = data.visit || {};
           const completionValue = visit.completion_status || 'Pending';
           const completionField = detailField('Completion', completionValue);
           const customerLink = visit.customer
               ? visitMasterLink('customer', visit.customer, visit.customer_name || visit.customer)
               : visit.custom_lead
                   ? visitMasterLink('lead', visit.custom_lead, visit.party_name || visit.custom_lead)
                   : escapeDetailsHtml(visit.party_name || 'Not specified');
           const address = visit.address_text || visit.customer_address || 'Not specified';
           const detailsBody = `<div class="maintenance-detail-grid">${detailField('Visit', visit.name, { link: 'maintenance-visit' })}${detailField('Visit Type', visit.maintenance_type)}<div class="maintenance-detail-field"><span class="maintenance-detail-field-label">${escapeDetailsHtml(visit.party_label || 'Customer')}</span><span class="maintenance-detail-field-value">${customerLink}</span></div>${completionField}${detailField('Scheduling Status', visit.custom_scheduling_status || 'Unscheduled')}${detailField('Document Status', visit.status || 'Draft')}${detailField('Created', visit.creation_display)}${detailField('Maintenance Date', visit.mntc_date)}${detailField('Maintenance Time', visit.mntc_time_display || 'Not scheduled')}${detailField('Company', visit.company)}${visit.maintenance_schedule ? detailField('Maintenance Schedule', visit.maintenance_schedule, { link: 'maintenance-schedule' }) : ''}${visit.contact_person || visit.contact_text ? detailField('Contact Person', visit.contact_text || visit.contact_person) : ''}${visit.contact_mobile ? detailField('Contact Phone', visit.contact_mobile) : ''}${visit.contact_email ? detailField('Contact Email', visit.contact_email, { email: true }) : ''}${detailField('Customer Address', address)}${visit.territory ? detailField('Territory', visit.territory) : ''}${visit.customer_group ? detailField('Customer Group', visit.customer_group) : ''}</div>${visit.description ? `<div class="maintenance-detail-field"><span class="maintenance-detail-field-label">Description</span><div class="maintenance-detail-field-value">${escapeDetailsHtml(visit.description)}</div></div>` : ''}`;

           const detailsBodyWithRichText = visit.description
               ? detailsBody.replace(escapeDetailsHtml(visit.description), renderRichText(visit.description))
               : detailsBody;
           const table = (headers, rows, renderRow, emptyText) => {
               const body = rows && rows.length ? rows.map(renderRow).join('') : `<tr><td colspan="${headers.length}" class="text-center text-muted">${escapeDetailsHtml(emptyText)}</td></tr>`;
               return `<div class="table-responsive"><table class="table table-striped table-bordered"><thead><tr>${headers.map((header) => `<th>${escapeDetailsHtml(header)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
           };
           const imageCell = (url, alt) => url ? `<a href="${escapeDetailsHtml(url)}" target="_blank" rel="noopener"><img src="${escapeDetailsHtml(url)}" class="maintenance-inline-image" alt="${escapeDetailsHtml(alt || 'Visit image')}"></a>` : 'No image';
           const productsBody = `<h5>Products</h5>${table(['Item Code', 'Item Name', 'Serial No', 'Image'], data.products || [], (row) => `<tr><td>${row.item_code ? visitMasterLink('item', row.item_code) : 'Not specified'}</td><td>${escapeDetailsHtml(row.item_name || '')}</td><td>${row.serial_no ? visitMasterLink('serial-no', row.serial_no) : 'Not specified'}</td><td>${row.custom_image ? imageCell(row.custom_image, 'Product image') : ''}</td></tr>`, 'No products available.')}`
               + `<h5>Spare Items</h5>${table(['Item Code', 'Description', 'Periodicity', 'UOM'], data.spare_items || [], (row) => `<tr><td>${row.item_code ? visitMasterLink('item', row.item_code) : 'Not specified'}</td><td>${escapeDetailsHtml(row.description || '')}</td><td>${escapeDetailsHtml(row.periodicity || '')}</td><td>${escapeDetailsHtml(row.uom || '')}</td></tr>`, 'No spare items available.')}`;
           const symptomsBody = table(['Item Code', 'Symptom Code', 'Resolution', 'Attach Image', 'Serial No.'], data.symptoms || [], (row) => `<tr><td>${row.item_code ? visitMasterLink('item', row.item_code) : 'Not specified'}</td><td>${escapeDetailsHtml(row.symptom_code || 'Not specified')}</td><td>${escapeDetailsHtml(row.resolution || 'Not specified')}</td><td>${imageCell(row.image, 'Symptom attachment')}</td><td>${row.serial_no ? visitMasterLink('serial-no', row.serial_no) : 'Not specified'}</td></tr>`, 'No symptoms or resolutions are available.');
           const commentsBody = (data.comments || []).length
               ? data.comments.map((comment) => `<div class="border-bottom mb-3 pb-2"><div>${escapeDetailsHtml(comment.content)}</div><small class="text-muted">${escapeDetailsHtml(comment.comment_by || comment.owner)} · ${escapeDetailsHtml(comment.creation_display)}</small></div>`).join('')
               : emptyDetail('No comments are available.');
           const attachmentsBody = (data.attachments || []).length
               ? `<div class="d-flex flex-wrap" style="gap:16px">${data.attachments.map((attachment) => `<figure>${imageCell(attachment.image, attachment.caption || 'Attached image')}${attachment.caption ? `<figcaption>${escapeDetailsHtml(attachment.caption)}</figcaption>` : ''}</figure>`).join('')}</div>`
               : emptyDetail('No attached images are available.');
           const symptomRequestCount = (data.symptom_requests || []).length;
           const requestsBody = table(['Item Code', 'Symptom Code', 'Resolution', 'Image', 'Status', 'Action'], data.symptom_requests || [], (row) => `<tr><td>${row.item_code ? visitMasterLink('item', row.item_code) : 'Not specified'}</td><td>${escapeDetailsHtml(row.symptom_code || '')}</td><td>${escapeDetailsHtml(row.resolution || '')}</td><td>${row.image ? imageCell(row.image, 'Symptom request image') : ''}</td><td>${escapeDetailsHtml(row.status || '')}</td><td>${visit.can_write && row.status === 'UnApproved' ? `<button type="button" class="btn btn-xs btn-primary approve-visit-symptom-request" data-visit="${escapeDetailsHtml(visit.name || '')}" data-request="${escapeDetailsHtml(row.name || '')}">Approve</button>` : ''}</td></tr>`, 'No symptom requests are available.');
           const notesBody = visit.service_tech_notes ? `<p>${escapeDetailsHtml(visit.service_tech_notes)}</p>` : emptyDetail('No technician notes are available.');
           const tabs = [
               ['details', 'Details', detailsBodyWithRichText],
               ['checklist', 'Checklist Tree', renderChecklistDetails(data)],
               ['products', 'Product and Services', productsBody],
               ['symptoms', 'Symptoms and resolutions', symptomsBody],
               ['comments', 'Comments', commentsBody],
               ['attachments', 'Attached Images', attachmentsBody],
               ['requests', 'Symptom Requests', requestsBody],
               ['notes', 'Technician Notes', notesBody],
           ];
           return `<div class="maintenance-inline-panel" data-issue="${escapeDetailsHtml(visit.name || '')}"><ul class="nav nav-tabs" role="tablist">${tabs.map(([key, label], index) => `<li class="nav-item"><a class="nav-link${index === 0 ? ' active' : ''}" href="javascript:void(0)" aria-controls="visit-tab-${key}" aria-selected="${index === 0 ? 'true' : 'false'}">${escapeDetailsHtml(label)}${key === 'requests' && symptomRequestCount ? `<span class="maintenance-request-dot" title="${symptomRequestCount} symptom request${symptomRequestCount === 1 ? '' : 's'}" aria-label="${symptomRequestCount} symptom requests"></span>` : ''}</a></li>`).join('')}</ul><div class="tab-content">${tabs.map(([key, label, body], index) => `<div class="tab-pane fade${index === 0 ? ' show active' : ''}" id="visit-tab-${key}" role="tabpanel">${body}</div>`).join('')}</div></div>`;
       }

       let activeMaintenanceVisitRequest = 0;
       function showInlineMaintenanceDetails(issueId, activeTab) {
           const wrapper = $('#maintenance-inline-detail-wrapper');
           const content = $('#maintenance-inline-detail-content');
           const visitRow = $('.maintenance-visit-card[data-issue="' + issueId + '"]');


           if (!wrapper.length || !content.length || !visitRow.length) {
               console.error('Maintenance Visit details panel or visit row was not found for:', issueId);
               return;
           }
           const requestId = ++activeMaintenanceVisitRequest;


           wrapper.removeClass('d-none');
           $('body').addClass('maintenance-details-open');
           const visitType = visitRow.attr('data-visit-type') || 'Maintenance Visit';
           const party = visitRow.find('.horizontal-visit-party').text().replace(/\s+/g, ' ').trim();
           const completion = visitRow.attr('data-completion') || 'Pending';
           $('#maintenance-detail-title').text(issueId);
           $('#maintenance-detail-subtitle').text(party ? visitType + ' · ' + party : visitType);
           $('#maintenance-detail-status')
               .text(completion)
               .attr('data-status', completion.toLowerCase().replace(/\s+/g, '-'))
               .prop('hidden', false);
           setBoardVisitSelection(issueId);


           $('#close-maintenance-inline-detail').trigger('focus');

           if (maintenanceVisitDetailsCache.has(issueId)) {
               content.html(maintenanceVisitDetailsCache.get(issueId));
               if (activeTab) content.find('.nav-link[aria-controls="visit-tab-' + activeTab + '"]').trigger('click');
               return;
           }

           content.html('<div class="maintenance-inline-empty">Loading visit details…</div>');
           frappe.call({
               method: 'field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.get_maintenance_visit_board_details',
               args: { visit_name: issueId },
               callback: function (response) {
                   if (requestId !== activeMaintenanceVisitRequest || !response.message) return;
                   const rendered = renderMaintenanceVisitDetails(response.message);
                   maintenanceVisitDetailsCache.set(issueId, rendered);
                   content.html(rendered);
                   if (activeTab) content.find('.nav-link[aria-controls="visit-tab-' + activeTab + '"]').trigger('click');
               },
               error: function () {
                   if (requestId !== activeMaintenanceVisitRequest) return;
                   content.html('<div class="maintenance-inline-empty">Could not load this visit. Close the panel and try again.</div>');
               }
           });
       }


       function closeMaintenanceDetails() {
           $('#maintenance-inline-detail-wrapper').addClass('d-none');
           $('body').removeClass('maintenance-details-open');
           $('#maintenance-inline-detail-content').html(
               '<div class="maintenance-inline-empty">Select a Maintenance Visit to view its details.</div>'
           );
           $('#maintenance-detail-subtitle').text('');
           $('#maintenance-detail-title').text('Maintenance Visit details');
           $('#maintenance-detail-status').text('').removeAttr('data-status').prop('hidden', true);
           setBoardVisitSelection(null);
       }


       $(document).on('click', '.show-inline-details', function (event) {
           event.preventDefault();
           event.stopPropagation();
           showInlineMaintenanceDetails($(this).data('issue'));
       });

       function assignmentDateValue() {
           const calendarDate = String($('.drop-zone[data-date]').first().attr('data-date') || '').trim();
           if (calendarDate) return calendarDate;
           const now = new Date();
           const month = String(now.getMonth() + 1).padStart(2, '0');
           const day = String(now.getDate()).padStart(2, '0');
           return now.getFullYear() + '-' + month + '-' + day;
       }

       function assignmentTimeValue(minutes) {
           const safeMinutes = Math.max(0, Math.min(23 * 60 + 30, minutes));
           return String(Math.floor(safeMinutes / 60)).padStart(2, '0') + ':'
               + String(safeMinutes % 60).padStart(2, '0');
       }

       function assignmentTimeDefaults() {
           const now = new Date();
           const roundedMinutes = Math.ceil((now.getHours() * 60 + now.getMinutes()) / 30) * 30;
           const startMinutes = Math.max(9 * 60, Math.min(19 * 60 + 30, roundedMinutes));
           return {
               start: assignmentTimeValue(startMinutes),
               end: assignmentTimeValue(Math.min(20 * 60, startMinutes + 30)),
           };
       }

       function selectedAssignmentTechnicians() {
           const values = $('#visit-assign-technician').val();
           const selected = Array.isArray(values) ? values : [values];
           return selected.map(function (value) {
               return String(value || '').trim();
           }).filter(Boolean);
       }

       const schedulingConflictsMethod = 'field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.get_scheduling_conflicts';
       let availabilityRequestSequence = 0;

       function refreshAssignmentAvailability(form) {
           if (!form || !form.length) return;
           let panel = form.find('.calendar-task-availability');
           if (!panel.length) {
               panel = $('<div class="calendar-task-availability" role="status" hidden></div>')
                   .css({ borderRadius: '10px', marginTop: '12px', padding: '10px 12px', maxHeight: '150px', overflowY: 'auto' })
                   .insertAfter(form.find('.calendar-task-time-grid'));
           }

           const techniciansValue = form.find('.technician').val();
           const technicians = (Array.isArray(techniciansValue) ? techniciansValue : [techniciansValue])
               .map(value => String(value || '').trim()).filter(Boolean);
           const code = String(form.find('[name="code"]').val() || '').trim();
           const date = String(form.find('[name="date"]').val() || '').trim();
           const stime = String(form.find('[name="stime"]').val() || '').trim();
           const etime = String(form.find('[name="etime"]').val() || '').trim();
           const buttons = form.find('#submit-visit-assign, .submit');
           const sequence = ++availabilityRequestSequence;
           form.data('availability-request-sequence', sequence);

           if (!technicians.length || !date || !stime || !etime) {
               panel.empty().prop('hidden', true);
               buttons.prop('disabled', false);
               return;
           }

           panel.css({ background: '#f8fafc', border: '1px solid #cbd5e1', color: '#475569' })
               .text('Checking technician availability…').prop('hidden', false);
           buttons.prop('disabled', true);

           const checks = technicians.map(function (technician) {
               return new Promise(function (resolve) {
                   frappe.call({
                       method: schedulingConflictsMethod,
                       args: { technician: technician, date: date, stime: stime, etime: etime, exclude_issue: code },
                       callback: response => resolve({ technician: technician, data: response && response.message }),
                       error: () => resolve({ technician: technician, failed: true }),
                   });
               });
           });

           Promise.all(checks).then(function (results) {
               if (form.data('availability-request-sequence') !== sequence) return;
               const failed = results.some(result => result.failed || !result.data);
               const conflicts = [];
               results.forEach(function (result) {
                   const option = form.find('.technician option').filter(function () {
                       return this.value === result.technician;
                   }).first();
                   const technicianLabel = option.length ? option.text().trim() : result.technician;
                   (result.data && result.data.conflicts || []).forEach(function (conflict) {
                       const period = [conflict.start, conflict.end].filter(Boolean).join('–');
                       const detail = conflict.detail ? ' · ' + conflict.detail : '';
                       conflicts.push(technicianLabel + ': ' + (conflict.label || 'Unavailable') + ' · ' + period + detail);
                   });
               });

               panel.empty();
               if (conflicts.length) {
                   panel.css({ background: '#fff7ed', border: '1px solid #fdba74', color: '#9a3412' })
                       .append($('<strong>').text('Selected time is unavailable. Change the technician or time.'));
                   conflicts.forEach(message => panel.append($('<div>').css('marginTop', '4px').text(message)));
                   panel.prop('hidden', false);
                   buttons.prop('disabled', true);
                   return;
               }

               if (failed) {
                   panel.css({ background: '#fffbeb', border: '1px solid #fcd34d', color: '#92400e' })
                       .text('Availability could not be checked. The server will validate this assignment when you save.')
                       .prop('hidden', false);
               } else {
                   panel.prop('hidden', true);
               }
               buttons.prop('disabled', false);
           });
       }

       $(document).on('change input', '#visit-assign-form .technician, #visit-assign-form [name="date"], #visit-assign-form [name="stime"], #visit-assign-form [name="etime"], .custom-form .technician, .custom-form [name="date"], .custom-form [name="stime"], .custom-form [name="etime"]', function () {
           refreshAssignmentAvailability($(this).closest('form'));
       });

       function closeVisitAssignmentDialog() {
           const modal = $('#visit-assign-modal');
           modal.removeClass('show').addClass('hide').attr('aria-hidden', 'true');
           $('body').removeClass('visit-assignment-open');
           $('#visit-assign-error').empty();
       }

       function openVisitAssignmentDialog(visitId) {
           const modal = $('#visit-assign-modal');
           const row = $('.maintenance-visit-card[data-issue="' + visitId + '"]');
           if (!modal.length || !row.length) return;

           $('#visit-assign-code').val(visitId);
           $('#visit-assign-code-display').val(visitId);
           $('#visit-assign-date').val(assignmentDateValue());
           const defaults = assignmentTimeDefaults();
           $('#visit-assign-start').val(defaults.start);
           $('#visit-assign-end').val(defaults.end);
           $('#visit-assign-title').text(visitId);
           $('#visit-assign-error').empty();
           $('#visit-assign-technician').val([]).trigger('change');
           modal.removeClass('hide').addClass('show').attr('aria-hidden', 'false');
           $('body').addClass('visit-assignment-open');
           window.setTimeout(function () {
               $('#visit-assign-technician').trigger('focus');
           }, 0);
       }

       $(document).on('click', '.assign-visit', function (event) {
           event.preventDefault();
           event.stopPropagation();
           const visitId = String($(this).attr('data-visit') || '').trim();
           if (visitId) openVisitAssignmentDialog(visitId);
       });

       $(document).on('click', '#close-visit-assign, #cancel-visit-assign', function (event) {
           event.preventDefault();
           closeVisitAssignmentDialog();
       });

       $(document).on('click', '#visit-assign-modal', function (event) {
           if (event.target === this) closeVisitAssignmentDialog();
       });

       $(document).on('submit', '#visit-assign-form', function (event) {
           event.preventDefault();
           const button = $('#submit-visit-assign');
           const error = $('#visit-assign-error');
           const code = String($('#visit-assign-code').val() || '').trim();
           const technicians = selectedAssignmentTechnicians();
           const date = String($('#visit-assign-date').val() || '').trim();
           const stime = String($('#visit-assign-start').val() || '').trim();
           const etime = String($('#visit-assign-end').val() || '').trim();
           const startMinutes = stime ? stime.split(':').map(Number) : [];
           const endMinutes = etime ? etime.split(':').map(Number) : [];
           const startValue = startMinutes.length === 2 ? startMinutes[0] * 60 + startMinutes[1] : 0;
           const endValue = endMinutes.length === 2 ? endMinutes[0] * 60 + endMinutes[1] : 0;

           error.empty();
           if (!code || !technicians.length || !date || !stime || !etime) {
               error.text('Choose at least one technician, a date, a start time, and an end time.');
               return;
           }
           if (startValue >= endValue) {
               error.text('End time must be later than start time.');
               return;
           }
           if (startValue % 30 !== 0 || endValue % 30 !== 0) {
               error.text('Use half-hour time slots, such as 10:00 or 10:30.');
               return;
           }

           button.prop('disabled', true).text('Scheduling...');
           frappe.call({
               method: 'field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.save_form_data',
               args: {
                   form_data: JSON.stringify({
                       code: code,
                       technicians: technicians,
                       date: date,
                       stime: stime,
                       etime: etime,
                   }),
               },
               callback: function (response) {
                   const result = response && response.message ? response.message : {};
                   if (result.success) {
                       closeVisitAssignmentDialog();
                       window.location.reload();
                       return;
                   }
                   error.text(result.message || 'The visit could not be scheduled. Try another time slot.');
                   button.prop('disabled', false).text('Schedule visit');
               },
               error: function () {
                   error.text('The visit could not be scheduled. Please try again.');
                   button.prop('disabled', false).text('Schedule visit');
               },
           });
       });

       $(document).on('click', '.create-visit-issue', function (event) {
           event.preventDefault();
           event.stopPropagation();

           const button = $(this);
           const visitId = String(button.attr('data-visit') || '').trim();
           if (!visitId) return;

           const issueOptions = {
               subject: 'Maintenance Visit ' + visitId,
               description: 'Issue raised against Maintenance Visit ' + visitId + '.',
               custom_maintenance_visit: visitId,
           };
           const customer = String(button.attr('data-customer') || '').trim();
           if (customer) issueOptions.customer = customer;

           frappe.new_doc('Issue', issueOptions);
       });


       $(document).on('click', '.maintenance-visit-card', function (event) {
           if ($(event.target).closest('a, .board-row-completion').length) {
               return;
           }
           showInlineMaintenanceDetails($(this).data('issue'));
       });


       $(document).on('click', '#close-maintenance-inline-detail', function () {
           closeMaintenanceDetails();
       });


       $(document).on('click', '#maintenance-inline-detail-wrapper', function (event) {
           if (event.target === this) {
               closeMaintenanceDetails();
           }
       });


       $(document).on('keydown', function (event) {
           if (event.key === 'Escape' && !$('#maintenance-inline-detail-wrapper').hasClass('d-none')) {
               closeMaintenanceDetails();
           }
           if (event.key === 'Escape' && !$('#visit-assign-modal').hasClass('hide')) {
               closeVisitAssignmentDialog();
           }
       });


       $(document).on('click', '#maintenance-inline-detail-content .nav-link', function (event) {
           event.preventDefault();
           const panel = $(this).closest('.maintenance-inline-panel');
           const contentId = $(this).attr('aria-controls');


           panel.find('.nav-link').removeClass('active').attr('aria-selected', 'false');
           panel.find('.tab-pane').removeClass('show active');
           $(this).addClass('active').attr('aria-selected', 'true');
           panel.find('#' + contentId).addClass('show active');
       });

       $(document).on('change', '.board-row-completion', function () {
           const field = $(this);
           const visitName = field.attr('data-visit');
           const requestedStatus = field.val();
           const visitRow = field.closest('.maintenance-visit-card');
           const previousStatus = visitRow.attr('data-completion') || '';
           field.prop('disabled', true);
           frappe.call({
               method: 'field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.update_visit_board_completion_status',
               args: { visit_name: visitName, completion_status: requestedStatus },
               callback: function (response) {
                   const savedStatus = response.message && response.message.completion_status;
                   if (!savedStatus) {
                       field.prop('disabled', false);
                       return;
                   }
                   visitRow.attr('data-completion', savedStatus);
                   field.attr('data-current-value', savedStatus);
                   $('#maintenance-detail-status').text(savedStatus).attr('data-status', savedStatus.toLowerCase().replace(/\s+/g, '-'));
                   field.val(savedStatus);
                   $('#maintenance-inline-detail-content .maintenance-detail-field').filter(function () {
                       return $(this).find('.maintenance-detail-field-label').text() === 'Completion';
                   }).find('.maintenance-detail-field-value').text(savedStatus);
                   field.prop('disabled', false);
                   maintenanceVisitDetailsCache.delete(visitName);
                   frappe.show_alert({ message: __('Visit status updated'), indicator: 'green' });
               },
               error: function () {
                   field.val(previousStatus);
                   field.prop('disabled', false);
                   frappe.show_alert({ message: __('Could not update visit status'), indicator: 'red' });
               }
           });
       });

       $(document).on('dragstart', '.board-row-completion', function (event) {
           event.preventDefault();
       });

       $(document).on('click', '#maintenance-inline-detail-content .approve-visit-symptom-request', function () {
           const button = $(this);
           const visitName = button.attr('data-visit');
           const requestName = button.attr('data-request');
           button.prop('disabled', true).text(__('Approving…'));
           frappe.call({
               method: 'field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.approve_visit_symptom_request',
               args: { visit_name: visitName, request_name: requestName },
               callback: function () {
                   maintenanceVisitDetailsCache.delete(visitName);
                   showInlineMaintenanceDetails(visitName, 'requests');
                   frappe.show_alert({ message: __('Symptom request approved'), indicator: 'green' });
               },
               error: function () {
                   button.prop('disabled', false).text(__('Approve'));
               }
           });
       });


       // OLD: Checklist rows were a static list, so headings could not reveal
       // their sub-steps, completion details, remarks, or attachments.
       $(document).on('click', '#maintenance-inline-detail-content .checklist-preview-step-toggle', function () {
           const toggle = $(this);
           const bodyId = toggle.attr('aria-controls');
           const body = $('#' + bodyId);
           const shouldExpand = toggle.attr('aria-expanded') !== 'true';


           toggle.attr('aria-expanded', shouldExpand ? 'true' : 'false');
           body.prop('hidden', !shouldExpand);
       });


       $(document).on('click', '#maintenance-inline-detail-content .checklist-preview-image-button', function (event) {
           event.preventDefault();
           event.stopPropagation();


           const imageUrl = $(this).attr('data-image');
           if (!imageUrl) {
               return;
           }


           const imageDialog = new frappe.ui.Dialog({
               title: __('Checklist Image'),
               size: 'large',
               fields: [
                   {
                       fieldname: 'image_preview',
                       fieldtype: 'HTML'
                   }
               ]
           });


           const imageWrapper = $('<div>').css({
               'text-align': 'center'
           });
           $('<img>')
               .attr({
                   src: imageUrl,
                   alt: __('Checklist image')
               })
               .css({
                   'border': '1px solid #dfe2e5',
                   'border-radius': '8px',
                   'max-height': '70vh',
                   'max-width': '100%',
                   'object-fit': 'contain'
               })
               .appendTo(imageWrapper);


           imageDialog.show();
           imageDialog.fields_dict.image_preview.$wrapper.empty().append(imageWrapper);
       });


       $(document).on('click', '#mapModalBtn', function () {
           modal = $('#mapModal');
           modal.removeClass('hide').addClass('show');
           const mapContainerId = 'live-map-container';
           const mapDiv = $('#' + mapContainerId);


           liveMapMaintenance = [];
           liveMapMaintenanceLoaded = false;


           // Stop any previous live-map poll before starting a new one
           if (updateInterval) {
               clearInterval(updateInterval);
               updateInterval = null;
           }


           // Remove existing map instance if any (to prevent re-initialization error)
           if (liveMap) {
               liveMap.remove();
               liveMap = null;
           }


           // Initialize the map
           liveMap = L.map(mapContainerId).setView([10.790603876302452, 106.71873522574441], 13); // Initial view centered on India
           L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
               maxZoom: 19,
               attribution: '&copy; OpenStreetMap contributors'
           }).addTo(liveMap);


           // Define custom icons for technicians and maintenance visits
           const technicianIcon = L.icon({
               iconUrl: '/files/technician.png',
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


           const liveMapLayers = {
               technicians: {},
               maintenance: {},
               circles: []
           };


           function getTechnicianPopup(tech) {
               return `
                   <div style="font-family:Inter,Arial,sans-serif;line-height:1.4;">
                       <strong>${tech.technician_name}</strong><br>
                       <span style="color:#6B7280;font-size:12px;">
                           ${tech.technician}
                       </span><br><br>
                       <span style="font-size:12px;">
                           📍 ${Number(tech.latitude).toFixed(4)}, ${Number(tech.longitude).toFixed(4)}
                       </span><br>
                       <span style="font-size:12px;">
                           🕒 ${formatTechnicianTime(tech.time)}
                       </span>
                   </div>
               `;
           }


           function renderTechnicians(technicians) {
               const visibleTechnicians = new Set();


               technicians.forEach(tech => {
                   if (!tech.latitude || !tech.longitude) {
                       return;
                   }


                   const key = tech.technician || tech.technician_name;
                   const latLng = [tech.latitude, tech.longitude];
                   visibleTechnicians.add(key);


                   if (liveMapLayers.technicians[key]) {
                       liveMapLayers.technicians[key]
                           .setLatLng(latLng)
                           .bindPopup(getTechnicianPopup(tech));
                   } else {
                       liveMapLayers.technicians[key] = L.marker(latLng, { icon: technicianIcon })
                           .addTo(liveMap)
                           .bindPopup(getTechnicianPopup(tech));
                   }
               });


               Object.keys(liveMapLayers.technicians).forEach(key => {
                   if (!visibleTechnicians.has(key)) {
                       liveMap.removeLayer(liveMapLayers.technicians[key]);
                       delete liveMapLayers.technicians[key];
                   }
               });
           }


           function getMaintenanceIcon(visit) {
               let finalIcon = redIcon;
               if (visit.type == 'Fresh Installation') {
                   finalIcon = whiteIcon;
               } else if (visit.type == 'Scheduled') {
                   finalIcon = greenIcon;
               } else if (visit.type == 'Rescheduled') {
                   finalIcon = blackIcon;
               } else if (visit.type == 'Site Survey') {
                   finalIcon = blueIcon;
               }
               if (visit.status == 'Approval Pending') {
                   finalIcon = yellowIcon;
               }
               return finalIcon;
           }


           function clearMaintenanceLayers() {
               Object.keys(liveMapLayers.maintenance).forEach(key => {
                   liveMap.removeLayer(liveMapLayers.maintenance[key]);
               });
               liveMapLayers.maintenance = {};


               liveMapLayers.circles.forEach(circle => liveMap.removeLayer(circle));
               liveMapLayers.circles = [];
           }


           function renderMaintenance(maintenance) {
               clearMaintenanceLayers();


               maintenance.forEach(visit => {
                   let customerLat = null;
                   let customerLng = null;


                   if (visit.geolocation && visit.geolocation.features && Array.isArray(visit.geolocation.features)) {
                       visit.geolocation.features.forEach(function (feature) {
                           const { properties, geometry } = feature;
                           const [lng, lat] = geometry.coordinates;


                           if (Object.keys(properties).length === 0) {
                               customerLat = lat;
                               customerLng = lng;
                           } else if (properties.point_type === 'circle' && properties.radius) {
                               const circle = L.circle([lat, lng], {
                                   radius: properties.radius,
                                   color: 'blue',
                                   fillColor: '#30a0ff',
                                   fillOpacity: 0.3
                               }).addTo(liveMap).bindPopup(`<b>Circle with radius: ${properties.radius} meters</b>`);
                               liveMapLayers.circles.push(circle);
                           }
                       });
                   } else {
                       console.error('Geolocation data is not in the correct format or missing');
                   }


                   if (customerLat !== null && customerLng !== null) {
                       liveMapLayers.maintenance[visit.visit_id] = L.marker([customerLat, customerLng], { icon: getMaintenanceIcon(visit) })
                           .addTo(liveMap)
                           .bindPopup(`<b>Maintenance Visit</b><br>${visit.visit_id} - ${visit.type} - ${visit.status}<br><b>${visit.customer}</b><br>${visit.address}`);
                   }
               });
           }


           function renderLiveLocations(message) {
               const technicians = liveMapMaintenanceLoaded ? message : (message.technicians || []);
               const maintenance = liveMapMaintenanceLoaded ? liveMapMaintenance : (message.maintenance || []);


               renderTechnicians(technicians || []);


               if (!liveMapMaintenanceLoaded) {
                   liveMapMaintenance = maintenance;
                   liveMapMaintenanceLoaded = true;
                   renderMaintenance(maintenance);
               }
           }


           function fetchAndDisplayLocations() {
               frappe.call({
                   method: liveMapMaintenanceLoaded
                       ? "field_service_management.field_service_management.page.api.get_live_technicians"
                       : "field_service_management.field_service_management.page.api.get_live_locations",
                   callback: function (r) {
                       if (r.message) {
                           renderLiveLocations(r.message);
                       } else {
                           console.log("No data returned from the server.");
                       }
                   }
               });
           }


           if (liveMapPreloadData) {
               renderLiveLocations(liveMapPreloadData);
               fetchAndDisplayLocations();
           } else {
               fetchAndDisplayLocations();
           }


           updateInterval = setInterval(fetchAndDisplayLocations, 60 * 1000);
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


           $(document).on('dragstart', '.drag', function (event) {
               const draggable = $(this);
               event.originalEvent.dataTransfer.setData('text/plain', draggable.attr('id'));
               draggable.css('opacity', '0.5');
           });


           $(document).on('dragend', '.drag', function () {
               $(this).css('opacity', '1');
               $('.drop-zone.drop-hover').removeClass('drop-hover');
           });


           $(document).on('dragover', '.drop-zone', function (event) {
               event.preventDefault();
               const dropZone = $(this);
               dropZone.addClass('drop-hover');
           });


           $(document).on('dragleave', '.drop-zone', function () {
               const dropZone = $(this);
               dropZone.removeClass('drop-hover');
           });


           $(document).on('drop', '.drop-zone', function (event) {
               event.preventDefault();
               const dropZone = $(this);
               const cardId = event.originalEvent.dataTransfer.getData('text/plain');
               const not_available = dropZone.data('na');
               const slotTime = dropZone.data('time');
               const tech = dropZone.data('tech');
               const card = $(`#${cardId}`);
               dropZone.removeClass('drop-hover');


               if (card.data('type') === 'type1') {
                   openModal(cardId, slotTime, tech, not_available);
               } else if (card.data('type') === 'type2') {
                   const duration = card.data('duration');
                   openModal2(cardId, slotTime, tech, duration, not_available);
               }
           });


           function openModal(issueName, slot, tech, na) {
               const modalId = `formModal${issueName}`; // Construct the modal ID
               const modal = $(`#${modalId}`); // Select the modal using jQuery


               if (modal.length) { // Check if the modal exists
                   const currentDate = new Date();
                   const year = currentDate.getFullYear();
                   const month = String(currentDate.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
                   const day = String(currentDate.getDate()).padStart(2, '0');
                   modal.removeClass('hide').addClass('show');
                   const [hours, minutes, seconds] = slot.split(':').map(Number);
                   if (hours < 10) {
                       const stime_val = '0' + slot.substring(0, 4)
                       modal.find('.stime').val(stime_val);
                       modal.find('.etime').data('stime', slot.substring(0, 4));
                   } else {
                       modal.find('.stime').val(slot.substring(0, 5));
                       modal.find('.etime').data('stime', slot.substring(0, 5));
                   }
                   const startMinutes = hours * 60 + minutes;
                   modal.find('.etime').val(assignmentTimeValue(Math.min(20 * 60, startMinutes + 30)));
                   modal.find('.technician').val(tech).change();
                   if (typeof na === 'string') {
                       try {
                           na = JSON.parse(na.replace(/'/g, '"')); // Convert single quotes to double quotes and parse the string
                       } catch (e) {
                           console.error('Error parsing na:', e);
                       }
                       $.each(na, function (index, value) {
                           const option = modal.find('.technician option[value="' + value + '"]');


                           if (option.length) {
                               option.prop('disabled', true);
                               option.css('color', 'red');
                           }
                       });
                   } else {
                       modal.find('.technician option').prop('disabled', false).css('color', '');
                   }
                   const formattedDate = `${year}-${month}-${day}`;
                   modal.find('.date').val(formattedDate).change();
               } else {
                   console.error(`Modal with ID ${modalId} not found.`);
               }
           }




           function openModal2(issueName, slot, tech, duration, na) {
               const modalId = `taskModal${issueName}`; // Construct the modal ID
               const modal = $(`#${modalId}`); // Select the modal using jQuery
               if (modal.length) { // Check if the modal exists
                   // const modalInstance = new bootstrap.Modal(modal[0]); // Pass the raw DOM element to bootstrap.Modal
                   const currentDate = new Date();
                   const year = currentDate.getFullYear();
                   const month = String(currentDate.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
                   const day = String(currentDate.getDate()).padStart(2, '0');
                   // modalInstance.show(); // Show the modal
                   modal.removeClass('hide').addClass('show');
                   const [hours, minutes, seconds] = slot.split(':').map(Number);
                   let startTime = new Date();
                   startTime.setHours(hours, minutes, seconds);
                   let etime = new Date(startTime.getTime() + duration * 60 * 60 * 1000);
                   if (hours < 10) {
                       const stime_val = '0' + slot.substring(0, 4)
                       modal.find('.stime').val(stime_val);
                       modal.find('.etime').data('stime', slot.substring(0, 4));
                   } else {
                       modal.find('.stime').val(slot.substring(0, 5));
                       modal.find('.etime').data('stime', slot.substring(0, 5));
                   }
                   modal.find('.etime').val(etime.toTimeString().substring(0, 5));
                   modal.find('.technician').val(tech).change();
                   if (typeof na === 'string') {
                       try {
                           na = JSON.parse(na.replace(/'/g, '"')); // Convert single quotes to double quotes and parse the string
                       } catch (e) {
                           console.error('Error parsing na:', e);
                       }
                       $.each(na, function (index, value) {
                           const option = modal.find('.technician option[value="' + value + '"]');


                           if (option.length) {
                               option.prop('disabled', true);
                               option.css('color', 'red');
                           }
                       });
                   } else {
                       modal.find('.technician option').prop('disabled', false).css('color', '');
                   }
                   const formattedDate = `${year}-${month}-${day}`;
                   modal.find('.date').val(formattedDate).change();
               } else {
                   console.error(`Modal with ID ${modalId} not found.`);
               }
           }




       $(document).on('click', '.close', function () {
           const closedModal = $(this).closest('.modal');
           if (closedModal.attr('id') === 'mapModal' && updateInterval) {
               clearInterval(updateInterval);
               updateInterval = null;
               }
               if (closedModal.hasClass('calendar-task-modal')) {
                   closeCalendarTaskModal(closedModal);
               } else {
                   closedModal.removeClass('show').addClass('hide'); // Ensure the modal hides on close
               }
           });
           $(document).on('click', '.calendar-task-cancel', function () {
               const closedModal = $(this).closest('.modal');
               if (closedModal.hasClass('calendar-task-modal')) {
                   closeCalendarTaskModal(closedModal);
               } else {
                   closedModal.removeClass('show').addClass('hide');
               }
           });




           /* OLD GLOBAL MODAL TAB HANDLER
           $('.nav-link').on('click', function (event) {
               // Prevent default action
               event.preventDefault();


               $('.nav-link').removeClass('active');
               $('.tab-pane').removeClass('show active');


               $(this).addClass('active');


               var contentId = $(this).attr('aria-controls');


               $('#' + contentId).addClass('show active');
           });
           END OLD GLOBAL MODAL TAB HANDLER */
       }, 3000);


       //update modal
       $(document).on("click", ".update", function () {
           const issueId = $(this).data("issue");
           const form = $("#custom2-form-" + issueId);


           if (!form.find(".etime").val()) {
               alert("Please select an end time.");
               return;
           }


           // Collect form data
           const formData = {
               code: form.find(".code").val(),
               technicians: form.find(".technician").val(),
               date: form.find(".date").val(),
               stime: form.find(".stime").val(),
               etime: form.find(".etime").val()
           };


           // Make an API call to Frappe to save the data in your Doctype
           frappe.call({
               method: "field_service_management.field_service_management.page.schedule_board_today.schedule_board_today.update_form_data",
               args: {
                   form_data: formData
               },
               callback: function (response) {
                   if (response.message.success) {
                       alert("Maintenance Visit updated successfully!");
                       window.location.reload();
                   } else {
                       alert(`Form submission failed!" ${response.message.message}`);
                   }
               },
               error: function (error) {
                   console.error(error);
                   alert("An error occurred while submitting the form!");
               }
           });


       });


       // $(document).on("click", "#lead-tab", function(){
       //  $("#maintenance-tab").css("text-decoration", "none");
       //  $("#lead-tab").css("text-decoration", "underline");
       //  $("#maintenance-tab-body").css("display", "none");
       //  $("#lead-body").css("display", "block");
       // })
       // $(document).on("click", "#maintenance-tab", function() {
       //  $("#lead-tab").css("text-decoration", "none");
       //  $("#maintenance-tab").css("text-decoration", "underline");
      
       //  $("#lead-body").css("display", "none");
       //  $("#maintenance-tab-body").css("display", "block");
       // });




   });




}

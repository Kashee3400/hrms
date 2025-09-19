/**
 * Bulk Attendance Management JavaScript Module
 *
 * Dependencies: jQuery, Select2 (optional)
 *
 * Usage:
 * const bulkAttendance = new BulkAttendanceManager({
 *     formSelector: '#bulkAttendanceForm',
 *     employeeSelectSelector: '#id_employees',
 *     selectAllSelector: '#id_select_all',
 *     // ... other options
 * });
 * bulkAttendance.init();
 */

class BulkAttendanceManager {
    constructor(options = {}) {
        // Default configuration
        this.config = {
            formSelector: '#bulkAttendanceForm',
            employeeSelectSelector: '#id_employees',
            selectAllSelector: '#id_select_all',
            startDateSelector: '#id_start_date',
            endDateSelector: '#id_end_date',
            startTimeSelector: '#id_start_time',
            endTimeSelector: '#id_end_time',
            previewButtonSelector: '#preview-btn',
            validateButtonSelector: '#validate-btn',
            resetButtonSelector: 'button[type="reset"]',
            submitButtonSelector: 'button[type="submit"]',

            // Stats selectors
            statsStartDateSelector: '#stats_start_date',
            statsEndDateSelector: '#stats_end_date',
            loadStatsButtonSelector: '#loadStatsBtn',
            refreshStatsButtonSelector: '#refreshStatsBtn',

            // URLs (should be passed from template)
            attendanceStatsUrl: '/ajax/attendance-stats/',
            attendancePreviewUrl: '/ajax/attendance-preview/',
            employeesAjaxUrl: '/ajax/employees/',

            // Auto-save settings
            autoSaveInterval: 30000, // 30 seconds
            autoRefreshStatsInterval: 300000, // 5 minutes

            // Employee count (should be passed from template)
            totalEmployeeCount: 0,

            ...options
        };

        this.form = null;
        this.autoSaveTimer = null;
        this.autoRefreshTimer = null;
    }

    init() {
        this.form = $(this.config.formSelector);

        if (this.form.length === 0) {
            console.error('Bulk Attendance Form not found');
            return;
        }

        this.bindEvents();
        this.initializeAutoSave();
        this.initializeStats();
        this.updatePreview();
    }

    bindEvents() {
        // Select All Toggle
        $(this.config.selectAllSelector).on('change', (e) => {
            this.handleSelectAllToggle(e);
        });

        // Real-time form validation and preview updates
        $(`${this.config.formSelector} input, ${this.config.formSelector} select`).on('change input', (e) => {
            this.updatePreview();
            this.validateField($(e.target));
        });

        // Auto-update end date when start date changes
        $(this.config.startDateSelector).on('change', () => {
            this.handleStartDateChange();
        });

        // Preview button
        $(this.config.previewButtonSelector).on('click', (e) => {
            this.handlePreviewClick(e);
        });

        // Validate button
        $(this.config.validateButtonSelector).on('click', () => {
            this.validateForm();
        });

        // Form submission
        this.form.on('submit', (e) => {
            return this.handleFormSubmit(e);
        });

        // Reset button
        $(this.config.resetButtonSelector).on('click', () => {
            this.handleFormReset();
        });

        // Stats events
        $(this.config.loadStatsButtonSelector + ', ' + this.config.refreshStatsButtonSelector).on('click', () => {
            this.loadAttendanceStats();
        });

        $(this.config.statsStartDateSelector + ', ' + this.config.statsEndDateSelector).on('change', () => {
            this.loadAttendanceStats();
        });
    }

    handleSelectAllToggle(e) {
        const isChecked = $(e.target).is(':checked');
        const employeeSelect = $(this.config.employeeSelectSelector);

        if (isChecked) {
            employeeSelect.prop('disabled', true).val(null).trigger('change');
            employeeSelect.next('.select2-container').addClass('opacity-50');
        } else {
            employeeSelect.prop('disabled', false);
            employeeSelect.next('.select2-container').removeClass('opacity-50');
        }

        this.updatePreview();
    }

    handleStartDateChange() {
        const startDate = $(this.config.startDateSelector).val();
        const endDate = $(this.config.endDateSelector).val();

        if (startDate && (!endDate || endDate < startDate)) {
            $(this.config.endDateSelector).val(startDate);
            this.updatePreview();
        }
    }

    handlePreviewClick(e) {
        const $btn = $(e.currentTarget);
        $btn.find('.loading-spinner').show();
        this.updatePreview(true);

        setTimeout(() => {
            $btn.find('.loading-spinner').hide();
        }, 1000);
    }

    handleFormSubmit(e) {
        const isValid = this.validateForm();

        if (!isValid) {
            e.preventDefault();
            this.scrollToFirstError();
            return false;
        }

        const confirmMessage = this.getConfirmationMessage();
        if (!confirm(confirmMessage)) {
            e.preventDefault();
            return false;
        }

        // Show loading state
        this.form.find(this.config.submitButtonSelector).prop('disabled', true)
            .html('<i class="fas fa-spinner fa-spin me-2"></i>Processing...');

        return true;
    }

    handleFormReset() {
        $(this.config.employeeSelectSelector).val(null).trigger('change');
        $(this.config.selectAllSelector).prop('checked', false).trigger('change');
        $('.error-field').removeClass('error-field');
        $('.field-errors').remove();
        this.updatePreview();
    }

    updatePreview(detailed = false) {
        const formData = this.getFormData();

        if (!this.isValidPreviewData(formData)) {
            this.hidePreview();
            return;
        }

        // Calculate duration
        const startDateTime = new Date(`${formData.startDate}T${formData.startTime}`);
        const endDateTime = new Date(`${formData.endDate}T${formData.endTime}`);
        const durationMs = endDateTime - startDateTime;
        const durationHours = durationMs / (1000 * 60 * 60);

        if (durationHours <= 0) {
            this.hidePreview();
            return;
        }

        this.displayPreview({
            durationHours, formData, detailed
        });
    }

    getFormData() {
        return {
            startDate: $(this.config.startDateSelector).val(),
            endDate: $(this.config.endDateSelector).val(),
            startTime: $(this.config.startTimeSelector).val(),
            endTime: $(this.config.endTimeSelector).val(),
            selectAll: $(this.config.selectAllSelector).is(':checked'),
            selectedEmployees: $(this.config.employeeSelectSelector).val() || []
        };
    }

    isValidPreviewData(data) {
        return data.startDate && data.endDate && data.startTime && data.endTime;
    }

    hidePreview() {
        $('#preview-content').show();
        $('#preview-data').hide();
    }

    displayPreview({durationHours, formData, detailed}) {
        // Update preview display
        $('#duration-hours').text(`${durationHours.toFixed(1)} hours`);
        $('#date-range').text(`${formData.startDate} to ${formData.endDate}`);
        $('#time-range').text(`${formData.startTime} to ${formData.endTime}`);

        const employeeCount = formData.selectAll ? this.config.totalEmployeeCount : formData.selectedEmployees.length;
        $('#employee-count').text(`${employeeCount} selected`);
        $('#submit-count').text(employeeCount);

        // Update sample employee names
        this.updateSampleEmployees(formData);

        $('#preview-content').hide();
        $('#preview-data').show().addClass('fade-in');

        // Show existing records warning if detailed preview
        if (detailed && employeeCount > 0) {
            this.checkExistingRecords(formData);
        }
    }

    updateSampleEmployees(formData) {
        let sampleHtml = '';

        if (formData.selectAll) {
            sampleHtml = '<div class="employee-badge"><i class="fas fa-users me-1"></i>All Active Employees</div>';
        } else if (formData.selectedEmployees.length > 0) {
            const sampleNames = formData.selectedEmployees.slice(0, 4).map(id => {
                const optionText = $(`${this.config.employeeSelectSelector} option[value="${id}"]`).text();
                return optionText.split(' (')[0];
            });

            sampleNames.forEach(name => {
                sampleHtml += `<div class="employee-badge">${name}</div>`;
            });

            if (formData.selectedEmployees.length > 4) {
                sampleHtml += `<div class="employee-badge bg-secondary">+${formData.selectedEmployees.length - 4} more</div>`;
            }
        }

        $('#sample-employees').html(sampleHtml);
    }

    checkExistingRecords(formData) {
        $.ajax({
            url: this.config.attendancePreviewUrl,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                start_date: formData.startDate,
                end_date: formData.endDate,
                start_time: formData.startTime,
                end_time: formData.endTime,
                select_all: formData.selectAll,
                employee_ids: formData.selectedEmployees
            }),
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));
            },
            success: (response) => {
                if (response.success && response.existing_records > 0) {
                    $('#existing-count').text(response.existing_records);
                    $('#existing-records-warning').show();
                    // Update preview display
                    $('#duration-hours').text(`${durationHours.toFixed(1)} hours`);
                    $('#date-range').text(response.date_range);
                    $('#time-range').text(response.time_range);

                    $('#employee-count').text(`${response.employee_count} selected`);
                    $('#submit-count').text(employeeCount);
                    // Update sample employee names
                    let sampleHtml = '';
                    if (response.sample_employees.length > 0) {
                        if (selectedEmployees.length > 4) {
                            sampleHtml += `<div class="employee-badge bg-secondary">+${selectedEmployees.length - 4} more</div>`;
                        } else {
                            response.sample_employees.forEach(name => {
                                sampleHtml += `<div class="employee-badge">${name}</div>`;
                            });
                        }
                    }
                    $('#sample-employees').html(sampleHtml);

                }
            },
            error: (xhr, status, error) => {
                console.error('Preview check failed:', error);
            }
        });
    }

    validateField($field) {
        const fieldName = $field.attr('name');
        const fieldValue = $field.val();

        // Remove existing errors
        $field.removeClass('error-field').next('.field-errors').remove();

        // Basic client-side validation
        if ($field.prop('required') && !fieldValue) {
            this.showFieldError($field, 'This field is required.');
            return false;
        }

        // Date validation
        if (fieldName === 'end_date') {
            const startDate = $(this.config.startDateSelector).val();
            if (startDate && fieldValue && fieldValue < startDate) {
                this.showFieldError($field, 'End date must be after start date.');
                return false;
            }
        }

        // Time validation
        if (fieldName === 'end_time') {
            const startDate = $(this.config.startDateSelector).val();
            const endDate = $(this.config.endDateSelector).val();
            const startTime = $(this.config.startTimeSelector).val();

            if (startDate && endDate && startDate === endDate && startTime && fieldValue <= startTime) {
                this.showFieldError($field, 'End time must be after start time on the same day.');
                return false;
            }
        }

        return true;
    }

    validateForm() {
        let isValid = true;
        const requiredFields = ['start_date', 'end_date', 'start_time', 'end_time'];

        // Clear all existing errors
        $('.error-field').removeClass('error-field');
        $('.field-errors').remove();

        // Validate required fields
        requiredFields.forEach(fieldName => {
            const $field = $(`[name="${fieldName}"]`);
            if (!this.validateField($field)) {
                isValid = false;
            }
        });

        // Validate employee selection
        const formData = this.getFormData();
        if (!formData.selectAll && formData.selectedEmployees.length === 0) {
            this.showFieldError($(this.config.employeeSelectSelector), 'Please select at least one employee or check "Select All".');
            isValid = false;
        }

        return isValid;
    }

    showFieldError($field, message) {
        $field.addClass('error-field');
        $field.after(`<div class="field-errors"><i class="fas fa-exclamation-circle me-1"></i>${message}</div>`);
    }

    scrollToFirstError() {
        $('html, body').animate({
            scrollTop: $('.field-errors:first, .alert-danger:first').offset().top - 100
        }, 500);
    }

    getConfirmationMessage() {
        const formData = this.getFormData();
        const employeeCount = formData.selectAll ? this.config.totalEmployeeCount : formData.selectedEmployees.length;

        return `Are you sure you want to mark attendance as PRESENT for ${employeeCount} employee(s) from ${formData.startDate} to ${formData.endDate}?\n\nThis action will:\n- Create ${employeeCount} attendance records\n- Mark them as approved automatically\n- Set them as backend regularized\n\nClick OK to proceed.`;
    }

    // Auto-save functionality
    initializeAutoSave() {
        if (this.config.autoSaveInterval > 0) {
            this.autoSaveTimer = setInterval(() => {
                const formData = this.form.serialize();
                localStorage.setItem('bulkAttendanceFormData', formData);
            }, this.config.autoSaveInterval);
        }
    }

    // Stats functionality
    initializeStats() {
        this.loadAttendanceStats();

        if (this.config.autoRefreshStatsInterval > 0) {
            this.autoRefreshTimer = setInterval(() => {
                this.loadAttendanceStats();
            }, this.config.autoRefreshStatsInterval);
        }
    }

    loadAttendanceStats() {
        const startDate = $(this.config.statsStartDateSelector).val();
        const endDate = $(this.config.statsEndDateSelector).val();

        if (!startDate || !endDate) {
            this.showStatsError('Please select both start and end dates.');
            return;
        }

        if (startDate > endDate) {
            this.showStatsError('End date must be after start date.');
            return;
        }

        this.showStatsLoading();

        $.ajax({
            url: this.config.attendanceStatsUrl,
            method: 'GET',
            data: {start_date: startDate, end_date: endDate},
            success: (response) => {
                this.displayStats(response);
            },
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));
            },
            error: (xhr, status, error) => {
                let errorMessage = 'Failed to load statistics';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage = xhr.responseJSON.error;
                }
                this.showStatsError(errorMessage);
            }
        });
    }

    showStatsLoading() {
        $('#statsContainer, #statsError, #noStatsData').hide();
        $('#statsLoading').show();
    }

    showStatsError(message) {
        $('#statsContainer, #statsLoading, #noStatsData').hide();
        $('#statsErrorMessage').text(message);
        $('#statsError').show();
    }

    displayStats(data) {
        $('#statsLoading, #statsError').hide();

        if (data.total_logs === 0) {
            $('#statsContainer').hide();
            $('#noStatsData').show();
            return;
        }

        this.updateStatsDisplay(data);
        this.generateInsights(data);
        this.animateStatsCards();

        $('#noStatsData').hide();
        $('#statsContainer').show();
    }

    updateStatsDisplay(data) {
        // Update date range and counts
        $('#statsDateRange').text(data.date_range);
        $('#totalLogsCount').text(data.total_logs.toLocaleString());
        $('#presentLogsCount').text(data.present_logs.toLocaleString());
        $('#backendRegularizedCount').text(data.backend_regularized.toLocaleString());

        // Calculate and update percentages
        const presentPercentage = data.total_logs > 0 ? ((data.present_logs / data.total_logs) * 100).toFixed(1) : 0;
        const backendPercentage = data.total_logs > 0 ? ((data.backend_regularized / data.total_logs) * 100).toFixed(1) : 0;

        $('#presentPercentage').text(presentPercentage + '%');
        $('#backendPercentage').text(backendPercentage + '%');

        // Update progress bars
        $('#attendanceProgressBar').css('width', presentPercentage + '%').attr('aria-valuenow', presentPercentage);
        $('#attendanceRateText').text(presentPercentage + '%');
        $('#regularizedProgressBar').css('width', backendPercentage + '%').attr('aria-valuenow', backendPercentage);
        $('#regularizedRateText').text(backendPercentage + '%');
    }

    generateInsights(data) {
        const insights = [];
        const presentPercentage = data.total_logs > 0 ? ((data.present_logs / data.total_logs) * 100) : 0;
        const backendPercentage = data.total_logs > 0 ? ((data.backend_regularized / data.total_logs) * 100) : 0;

        // Attendance rate insights
        if (presentPercentage >= 95) {
            insights.push({
                type: 'positive',
                icon: 'fas fa-thumbs-up',
                text: `Excellent attendance rate at ${presentPercentage.toFixed(1)}%`
            });
        } else if (presentPercentage >= 85) {
            insights.push({
                type: 'positive', icon: 'fas fa-check', text: `Good attendance rate at ${presentPercentage.toFixed(1)}%`
            });
        } else if (presentPercentage >= 70) {
            insights.push({
                type: 'warning',
                icon: 'fas fa-exclamation',
                text: `Moderate attendance rate at ${presentPercentage.toFixed(1)}% - room for improvement`
            });
        } else {
            insights.push({
                type: 'negative',
                icon: 'fas fa-exclamation-triangle',
                text: `Low attendance rate at ${presentPercentage.toFixed(1)}% - needs attention`
            });
        }

        // Backend regularization insights
        if (backendPercentage > 50) {
            insights.push({
                type: 'warning',
                icon: 'fas fa-cogs',
                text: `High backend regularization rate (${backendPercentage.toFixed(1)}%) - consider process review`
            });
        } else if (backendPercentage > 0) {
            insights.push({
                type: 'positive',
                icon: 'fas fa-tools',
                text: `${backendPercentage.toFixed(1)}% of records were backend regularized`
            });
        }

        // Volume insights
        if (data.total_logs > 100) {
            insights.push({
                type: 'positive',
                icon: 'fas fa-chart-bar',
                text: `High activity period with ${data.total_logs.toLocaleString()} total attendance logs`
            });
        }

        // Render insights
        let insightsHtml = '';
        insights.forEach(insight => {
            insightsHtml += `
                <div class="insight-item ${insight.type}">
                    <i class="${insight.icon} me-2"></i>
                    ${insight.text}
                </div>
            `;
        });

        $('#insightsContainer').html(insightsHtml);
    }

    animateStatsCards() {
        $('.stats-card').each(function (index) {
            $(this).css('opacity', '0').delay(index * 100).animate({
                opacity: 1
            }, 300);
        });

        // Animate numbers
        $('.stats-number').each(function () {
            const $this = $(this);
            const countTo = parseInt($this.text().replace(/,/g, ''));

            $({countNum: 0}).animate({
                countNum: countTo
            }, {
                duration: 1000, easing: 'linear', step: function () {
                    $this.text(Math.floor(this.countNum).toLocaleString());
                }, complete: function () {
                    $this.text(countTo.toLocaleString());
                }
            });
        });
    }

    // Cleanup method
    destroy() {
        if (this.autoSaveTimer) {
            clearInterval(this.autoSaveTimer);
        }
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
        }

        // Unbind events
        $(this.config.formSelector).off();
        $(this.config.selectAllSelector).off();
        $(this.config.previewButtonSelector).off();
        $(this.config.validateButtonSelector).off();
        $(this.config.resetButtonSelector).off();
        $(this.config.loadStatsButtonSelector).off();
        $(this.config.refreshStatsButtonSelector).off();
        $(this.config.statsStartDateSelector).off();
        $(this.config.statsEndDateSelector).off();
    }
}

// Export for use in templates
window.BulkAttendanceManager = BulkAttendanceManager;
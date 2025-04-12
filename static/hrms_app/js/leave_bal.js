$(document).ready(function () {
    $('#forwardLeavesBtn').click(function () {
        const year = $('#yearInput').val();

        const $messageBox = $('#leaveForwardMessage');
        $messageBox.text('').removeClass('success error');

        // Validate input year
        if (!year || isNaN(year)) {
            $messageBox
                .text('Please enter a valid year.')
                .addClass('text-danger');
            return;
        }

        // Show loader while processing the request
        $('#loader').show();
        $('#forwardLeavesBtn').prop('disabled', true); // Disable the button

        $.ajax({
            url: '/api/v1/forward-leave-balances/',  // Update this URL to your API endpoint
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ year: parseInt(year) }),
            headers: {
                // CSRF token (if needed for Django)
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function (data) {
                // Hide loader and re-enable button
                $('#loader').hide();
                $('#forwardLeavesBtn').prop('disabled', false);

                // Success message
                $messageBox
                    .text(data.detail + ` (${data.records_created} new records created)`)
                    .removeClass('error')
                    .addClass('success');
            },
            error: function (xhr) {
                // Hide loader and re-enable button on error
                $('#loader').hide();
                $('#forwardLeavesBtn').prop('disabled', false);

                const response = xhr.responseJSON;
                let message = "Something went wrong. Please try again.";

                // Customize error message based on the response
                if (response?.detail) message = response.detail;
                if (response?.error) message = response.error;

                // Display error message
                $messageBox
                    .text(message)
                    .removeClass('success')
                    .addClass('error');
            }
        });
    });
    $('#creditELBtn').click(function () {
        const year = $('#elYearInput').val();
        const days = $('#elDaysInput').val() || 7.5;
        const $message = $('#elCreditMessage');
        const $loader = $('#elLoader');

        $message.removeClass('alert-success alert-danger d-block').addClass('d-none').text('');

        if (!year || year < 2000) {
            $message
                .removeClass('d-none')
                .addClass('alert alert-danger d-block')
                .text('Please enter a valid year (e.g., 2025).');
            return;
        }

        $loader.show();
        $.ajax({
            url: '/api/v1/credit-el-leaves/',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ year: parseInt(year), days: parseFloat(days) }),
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
            success: function (response) {
                $message
                    .removeClass('d-none alert-danger')
                    .addClass('alert alert-success d-block')
                    .text(response.detail);
                if (response.errors?.length) {
                    $message.append(`<br><small class="text-muted">Some errors: ${response.errors.join(', ')}</small>`);
                }
            },
            error: function (xhr) {
                const response = xhr.responseJSON;
                $message
                    .removeClass('d-none alert-success')
                    .addClass('alert alert-danger d-block')
                    .text(response?.error || 'Something went wrong.');
            },
            complete: function () {
                $loader.hide();
            }
        });
    });

    $('#checkLeaveDaysBtn').click(function () {
        const $result = $('#leaveDaysResult');
        const startDateRaw = $('#startDate').val();
        const endDateRaw = $('#endDate').val();
        const startDate = formatDateToYYYYMMDD(startDateRaw);
        const endDate = formatDateToYYYYMMDD(endDateRaw);
        $result.text(''); // Clear old result
        if (!startDate || !endDate) {
            $result.text('Please fill all fields.').addClass('text-danger');
            return;
        }

        $.ajax({
            url: '/api/v1/attendance-aggregation-count/',
            method: 'GET',
            data: {
                start_date: startDate,
                end_date: endDate,
            },
            success: function (data) {
                console.log("Formatted JSON:");
                console.log(JSON.stringify(data, null, 2));
                $result
                    .removeClass('text-danger')
                    .text(`Total Leave Days in Range: ${data.total_leave_days}`);
            },
            error: function (xhr) {
                const err = xhr.responseJSON?.error || "Something went wrong.";
                $result.addClass('text-danger').text(err);
            }
        });
    });
    function formatDateToYYYYMMDD(dateStr) {
        const date = new Date(dateStr);
        if (isNaN(date)) return null; // invalid date
        return date.toISOString().slice(0, 10); // YYYY-MM-DD
    }
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});

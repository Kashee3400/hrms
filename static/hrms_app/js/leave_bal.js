$(document).ready(function () {
    $('#creditELBtn').hide()
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
        const $message = $('#elCreditMessage');
        const $loader = $('#elLoader');
        $message.removeClass('alert-success alert-danger d-block').addClass('d-none').text('');
        $loader.show();

        // Collect selected employee codes and credit values
        const selectedData = [];
        $('#leaveStatusTable .rowCheckbox:checked').each(function () {
            const empCode = $(this).data('emp-code');
            const credit = parseFloat($(this).closest('tr').find('.creditValue').text());
            selectedData.push({ emp_code: empCode, balance: credit });
        });

        if (selectedData.length === 0) {
            $message
                .removeClass('d-none alert-success')
                .addClass('alert alert-danger d-block')
                .text('Please select at least one employee.');
            $loader.hide();
            return;
        }

        // Now send the selected data to the server
        $.ajax({
            url: '/api/v1/credit-el-leaves/',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ employees: selectedData}),
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
        $('#balance-loader').show()
        $.ajax({
            url: '/api/v1/attendance-aggregation-count/',
            method: 'GET',
            data: {
                start_date: startDate,
                end_date: endDate,
            },
            success: function (data) {
                $('#balance-loader').hide()
                $('#creditELBtn').show()
                const tableBody = $('#leaveStatusTable tbody');
                tableBody.empty();
                const keys = Object.keys(data.aggregated_status_counts);
                keys.forEach(empCode => {
                    const record = data.aggregated_status_counts[empCode];
                    const row = `
                        <tr>
                            <td><input type="checkbox" class="rowCheckbox" data-emp-code="${empCode}"/></td>
                            <td>${empCode}</td>
                            <td>${record.P || 0}</td>
                            <td>${record.H || 0}</td>
                            <td>${record.T || 0}</td>
                            <td>${record.CL || 0}</td>
                            <td>${record.CLH || 0}</td>
                            <td>${record.SL || 0}</td>
                            <td>${record.SLH || 0}</td>
                            <td>${record.FL || 0}</td>
                            <td>${record.EL || 0}</td>
                            <td>${record.TH || 0}</td>
                            <td>${record.OFF || 0}</td>
                            <td>${record.total || 0}</td>
                            <td class="creditValue">${(record.total / data.total_days * 7.5).toFixed(2)}</td>
                        </tr>
                    `;
                    tableBody.append(row);
                });

                // Show total days
                $('#leaveDaysResult')
                    .removeClass('text-danger')
                    .text(`Total Days from ${data.start_date} to ${data.end_date} is : ${data.total_days}`);
                $('.table').DataTable({
                    paging: true,
                    searching: true,
                    ordering: false,
                    dom: 'Bfrtip',
                    buttons: ['copy', 'csv', 'excel']
                })
            },
            error: function (xhr) {
                $('#balance-loader').hide()
                const err = xhr.responseJSON?.error || "Something went wrong.";
                $result.addClass('text-danger').text(err);
            }
        });
    });
    $(document).on('change', '#selectAll', function () {
        $('.rowCheckbox').prop('checked', $(this).prop('checked'));
    });

    $(document).on('change', '.rowCheckbox', function () {
        const allChecked = $('.rowCheckbox').length === $('.rowCheckbox:checked').length;
        $('#selectAll').prop('checked', allChecked);
    });
    function formatDateToYYYYMMDD(dateStr) {
        const date = new Date(dateStr);
        if (isNaN(date)) return null;

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
        const day = String(date.getDate()).padStart(2, '0');

        return `${year}-${month}-${day}`;
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

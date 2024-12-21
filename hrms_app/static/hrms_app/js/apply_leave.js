$(document).ready(function () {
    $('#balances').hide();
    $('#leave_type_div').hide();
    $('#choices').hide();
    
    $('#id_startDate').change(function () {
        var startDate = $(this).val();
        $('#id_endDate').val(startDate);
    });

    $('#id_startDate, #id_endDate').change(function () {
        var startDate = $('#id_startDate').val();
        var endDate = $('#id_endDate').val();
        var startDateObj = new Date(startDate);
        startDateObj.setDate(startDateObj.getDate() - 1);
        var minDate = startDateObj.toISOString().split('T')[0];
        $('#id_endDate').attr('data-min-date', minDate);
        totalDays = calculateTotalDays(startDate, endDate);
        bookedBalance = calculateBookedBalance(totalDays, startDate);
        $('#balances').show();
        // $('#choices').show();
    });

    $(document).on('change', '.leaveOption', function () {
        var selectId = $(this).attr('id');
        var selectedValue = $(this).val();
        var startDate = $('#id_startDate').val();
        var endDate = $('#id_endDate').val();
        if (selectId && selectId.startsWith('id_startDayChoice')) {
            startDay = selectedValue;
            if (startDate === endDate) {
                $('#id_endDayChoice').val(selectedValue);
                endDay = selectedValue;
            }
            $('#id_startDayChoice').val(selectedValue);
            updateTotalDays(startDay, endDay);
        } else if (selectId && selectId.startsWith('id_endDayChoice')) {
            endDay = selectedValue;
            if (startDate === endDate) {
                $('#id_startDayChoice').val(selectedValue);
                startDay = selectedValue;
            }
            $('#id_endDayChoice').val(selectedValue);
            updateTotalDays(startDay, endDay);
        }
    });
});

function updateTotalDays(startDay, endDay) {
    var startDate = $('#id_startDate').val();
    var endDate = $('#id_endDate').val();
    if (startDate == endDate) {
        if (startDay == 1) {
            $('#totalDays').text(totalDays);
            setBalance(leaveBalance, parseFloat($('#totalDays').text()));
        } else {
            $('#totalDays').text(totalDays - 0.5);
            setBalance(leaveBalance, parseFloat($('#totalDays').text()));
        }
    } else {
        // set total days if start and end day set to Full Day
        if (startDay == 1 && endDay == 1) {
            $('#totalDays').text(totalDays);
            setBalance(leaveBalance, parseFloat($('#totalDays').text()));
        }
        // set total day if start day is First Half or Second Half and end day is First Half
        else if (startDay == 2 && endDay == 2) {
            $('#totalDays').text(totalDays - 0.5);
            setBalance(leaveBalance, parseFloat($('#totalDays').text()));
        } else if (startDay == 3 && endDay == 2) {
            $('#totalDays').text(totalDays - 1);
            setBalance(leaveBalance, parseFloat($('#totalDays').text()));
        } else if (startDay == 3 && endDay == 1) {
            $('#totalDays').text(totalDays - 0.5);
            setBalance(leaveBalance, parseFloat($('#totalDays').text()));
        } else if (startDay == 1 && endDay == 2) {
            $('#totalDays').text(totalDays - 0.5);
            setBalance(leaveBalance, parseFloat($('#totalDays').text()));
        } else {
            $('#totalDays').text(totalDays);
            setBalance(leaveBalance, parseFloat($('#totalDays').text()));
        }
    }
}

// Function to calculate total number of days between two dates
function calculateTotalDays(startDate, endDate) {
    return generateDateOptions(startDate, endDate);
}

function calculateBookedBalance(totalDays, startDate) {
    var dateObject = new Date(startDate);
    // Create an array of month names
    var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    // Get day, month, and year from the date object
    var day = dateObject.getDate();
    var monthIndex = dateObject.getMonth();
    var year = dateObject.getFullYear();
    var formattedDate = day + '-' + monthNames[monthIndex] + '-' + year;
    $('#td_date').text('As of ' + formattedDate);
    setBalance(leaveBalance, totalDays);
    return 0;
}

function setBalance(typeBal, totalDays) {
    // $('#balance').text(typeBal);
    $('#currentlyBooked').text(totalDays);
    $('#remainingBal').text(typeBal - totalDays);
    $('#id_usedLeave').val(totalDays);
    $('#id_balanceLeave').val(typeBal - totalDays);
}

function generateDateOptions(startDate, endDate) {
    var currentDate = new Date(startDate);
    var endDateObj = new Date(endDate);
    var tableHTML = '<table class="table">';
    var totalDays = 0;
    while (currentDate <= endDateObj) {
        var formattedDate = currentDate.toDateString();
        var isStart = currentDate.toDateString() === new Date(startDate).toDateString();
        var isEnd = currentDate.toDateString() === new Date(endDate).toDateString();

        tableHTML += '<tr>';
        tableHTML += '<td class="formattedDate text-dark font-weight-bold">' + formattedDate + '</td>';
        tableHTML += '<td>';

        if (isStart) {
            tableHTML += '<select id="id_startDayChoice" class="leaveOption id_startDayChoice">';
            tableHTML += '<option value="1">Full Day</option>';
            tableHTML += '<option value="2">First Half</option>';
            tableHTML += '<option value="3">Second Half</option>';
            tableHTML += '</select>';
            totalDays++;
        } else if (isEnd) {
            tableHTML += '<select id="id_endDayChoice" class="leaveOption id_endDayChoice">';
            tableHTML += '<option value="1">Full Day</option>';
            tableHTML += '<option value="2">First Half</option>';
            tableHTML += '</select>';
            totalDays++;
        } else {
            tableHTML += '<select class="leaveOption">';
            tableHTML += '<option value="1">Full Day</option>';
            tableHTML += '</select>';
            totalDays++;
        }

        tableHTML += '</td>';
        tableHTML += '</tr>';
        // Move to the next date
        currentDate.setDate(currentDate.getDate() + 1);
    }

    tableHTML += '</table>';

    $('#dateOptions').html(tableHTML);
    $('#totalDays').text(totalDays);
    return totalDays;
}


function showToast(message, cls) {
    var toast = Metro.toast.create;
    toast(message, null, 5000, cls);
}
function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

$(document).ready(function () {
    calculateDuration();
    $('#id_reg_status').on('change', function () {
        var regStatus = $(this).val();
    });
    // Function to calculate the difference between two datetime fields
    function calculateDuration() {
        var fromDate = $('#id_from_date').val();
        var toDate = $('#id_to_date').val();
        if (fromDate && toDate) {
            var fromDateTime = new Date(fromDate);
            var toDateTime = new Date(toDate);
            if (fromDateTime <= toDateTime) {
                var diffMs = toDateTime - fromDateTime; // Difference in milliseconds
                var diffHours = Math.floor(diffMs / (1000 * 60 * 60));
                var diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
                var duration = diffHours + ':' + diffMinutes;
                $('#id_reg_duration').val(duration);
            } else {
                alert('From Date cannot be later than To Date.');
                $('#id_reg_duration').val('');
            }
        }
    }
    $(document).on('dp.change', function () {
        calculateDuration();
    });
});

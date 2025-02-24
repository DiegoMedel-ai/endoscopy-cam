$(document).ready(function(){
    $('#capture-btn').click(function(){
        $.ajax({
            url: '/video/capture',
            type: 'POST',
            success: function(response){
                $('#message').text(response.message);
            },
            error: function(){
                $('#message').text('Inicia una grabacion para capturar una imagen');
            }
        });
    });

    $('#start-btn').click(function(){
        $.ajax({
            url: '/video/start_recording',
            type: 'POST',
            success: function(response){
                var hiddenInput = document.getElementById("start-hour");
                if (hiddenInput) {
                    var now = new Date();
                    var hours = String(now.getHours()).padStart(2, '0');
                    var minutes = String(now.getMinutes()).padStart(2, '0');
                    var currentTime = hours + ':' + minutes;
                    hiddenInput.value = currentTime;
                }
                $('#message').text(response.message);
            },
            error: function(){
                $('#message').text('Error al iniciar la transmisión');
            }
        });
    });

    $('#stop-btn').click(function(){
        $.ajax({
            url: '/video/stop_recording',
            type: 'POST',
            success: function(response){
                $('#message').text(response.message);
            },
            error: function(){
                $('#message').text('Error al detener la transmisión');
            }
        });
    });
});



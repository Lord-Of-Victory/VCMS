let links = document.querySelectorAll('a');
for (let i = 0; i < links.length; i++) {
    links[i].addEventListener('click', function(event) {
        event.preventDefault();
        let filename = this.getAttribute('href').split('/').pop();
        let xhr = new XMLHttpRequest();
        xhr.open('GET', '/upload/' + filename);
        xhr.responseType = 'blob';
        xhr.onload = function() {
            let url = window.URL.createObjectURL(xhr.response);
            let a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            setTimeout(function() {
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            }, 0);
        };
        xhr.send();
    });
}

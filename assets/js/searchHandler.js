document.addEventListener('DOMContentLoaded', function () {
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('q');

    document.getElementById('query').textContent = query;

    fetch(`http://127.0.0.1:5000/search?q=${query}`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('summary').textContent = data.summary;

            const linksContainer = document.getElementById('links');
            data.links.forEach(link => {
                const listItem = document.createElement('li');
                const anchor = document.createElement('a');
                anchor.href = link;
                anchor.textContent = link;
                anchor.target = '_blank';
                listItem.appendChild(anchor);
                linksContainer.appendChild(listItem);
            });
        })
        .catch(error => {
            console.error('Error fetching results:', error);
        });
});

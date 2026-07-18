const PedidosDB = {
    DB_NAME: 'PedidosDB',
    DB_VERSION: 1,

    open() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('articulos')) {
                    db.createObjectStore('articulos', { keyPath: 'codigo' });
                }
                if (!db.objectStoreNames.contains('clientes')) {
                    db.createObjectStore('clientes', { keyPath: 'codigo' });
                }
                if (!db.objectStoreNames.contains('listas_precio')) {
                    db.createObjectStore('listas_precio', { keyPath: 'codigo' });
                }
                if (!db.objectStoreNames.contains('precios')) {
                    const store = db.createObjectStore('precios', { keyPath: ['articulo_codigo', 'lista_codigo'] });
                }
                if (!db.objectStoreNames.contains('pedidosPendientes')) {
                    db.createObjectStore('pedidosPendientes', { keyPath: 'temp_id', autoIncrement: true });
                }
                if (!db.objectStoreNames.contains('config')) {
                    db.createObjectStore('config', { keyPath: 'key' });
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    async saveData(data) {
        const db = await this.open();
        const stores = ['articulos', 'clientes', 'listas_precio', 'precios'];
        for (const storeName of stores) {
            if (data[storeName]) {
                const tx = db.transaction(storeName, 'readwrite');
                const store = tx.objectStore(storeName);
                store.clear();
                for (const item of data[storeName]) {
                    store.add(item);
                }
            }
        }
        const txConfig = db.transaction('config', 'readwrite');
        txConfig.objectStore('config').put({ key: 'lastSync', value: new Date().toISOString() });
    },

    async getArticulos() {
        const db = await this.open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('articulos', 'readonly');
            const request = tx.objectStore('articulos').getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    async getClientes() {
        const db = await this.open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('clientes', 'readonly');
            const request = tx.objectStore('clientes').getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    async getPrecios() {
        const db = await this.open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('precios', 'readonly');
            const request = tx.objectStore('precios').getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    async getListasPrecio() {
        const db = await this.open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('listas_precio', 'readonly');
            const request = tx.objectStore('listas_precio').getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    async savePedidoLocal(pedido) {
        const db = await this.open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('pedidosPendientes', 'readwrite');
            const request = tx.objectStore('pedidosPendientes').add(pedido);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    async getPedidosPendientes() {
        const db = await this.open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('pedidosPendientes', 'readonly');
            const request = tx.objectStore('pedidosPendientes').getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    async clearPedidosPendientes() {
        const db = await this.open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('pedidosPendientes', 'readwrite');
            const request = tx.objectStore('pedidosPendientes').clear();
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    },

    async getLastSync() {
        const db = await this.open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('config', 'readonly');
            const request = tx.objectStore('config').get('lastSync');
            request.onsuccess = () => resolve(request.result ? request.result.value : null);
            request.onerror = () => reject(request.error);
        });
    },

    async searchArticulos(texto) {
        const all = await this.getArticulos();
        const lower = texto.toLowerCase();
        return all.filter(a =>
            a.codigo.toLowerCase().includes(lower) ||
            a.descripcion.toLowerCase().includes(lower) ||
            (a.rubro && a.rubro.toLowerCase().includes(lower)) ||
            (a.marca && a.marca.toLowerCase().includes(lower))
        ).slice(0, 10);
    },

    async searchClientes(texto) {
        const all = await this.getClientes();
        const lower = texto.toLowerCase();
        return all.filter(c =>
            c.codigo.toLowerCase().includes(lower) ||
            c.razon_social.toLowerCase().includes(lower) ||
            (c.nombre_fantasia && c.nombre_fantasia.toLowerCase().includes(lower))
        ).slice(0, 10);
    },

    async getPrecioArticulo(clienteCodigo, articuloCodigo) {
        const clientes = await this.getClientes();
        const cliente = clientes.find(c => c.codigo === clienteCodigo);
        if (!cliente || !cliente.codigo_lista_precio) return 0;

        const precios = await this.getPrecios();
        const precio = precios.find(p =>
            p.articulo_codigo === articuloCodigo && p.lista_codigo === cliente.codigo_lista_precio
        );
        return precio ? precio.precio : 0;
    }
};

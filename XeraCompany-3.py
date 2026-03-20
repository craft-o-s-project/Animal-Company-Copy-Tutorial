import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading

# ---------------------------------------------------------------------------
# Admin GUI
# ---------------------------------------------------------------------------

class AdminGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Xera Backend Admin")
        self.root.geometry("1000x700")
        self.root.configure(bg='#1e1e2e')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame',       background='#1e1e2e')
        style.configure('TLabel',       background='#1e1e2e', foreground='#cdd6f4', font=('Consolas', 10))
        style.configure('TButton',      background='#313244', foreground='#cdd6f4', font=('Consolas', 10), borderwidth=0, padding=6)
        style.map('TButton',            background=[('active', '#45475a')])
        style.configure('TEntry',       fieldbackground='#313244', foreground='#cdd6f4', insertcolor='#cdd6f4', font=('Consolas', 10))
        style.configure('TNotebook',    background='#1e1e2e', borderwidth=0)
        style.configure('TNotebook.Tab',background='#313244', foreground='#cdd6f4', font=('Consolas', 10), padding=[10, 4])
        style.map('TNotebook.Tab',      background=[('selected', '#45475a')])
        style.configure('Treeview',     background='#313244', foreground='#cdd6f4', fieldbackground='#313244', font=('Consolas', 10), rowheight=24)
        style.configure('Treeview.Heading', background='#45475a', foreground='#cdd6f4', font=('Consolas', 10, 'bold'))
        style.map('Treeview',           background=[('selected', '#585b70')])

        # Notebook tabs
        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_users    = ttk.Frame(notebook)
        self.tab_currency = ttk.Frame(notebook)
        self.tab_bans     = ttk.Frame(notebook)
        self.tab_logs     = ttk.Frame(notebook)

        notebook.add(self.tab_users,    text='👥  Users')
        notebook.add(self.tab_currency, text='💰  Currency')
        notebook.add(self.tab_bans,     text='🔨  Bans')
        notebook.add(self.tab_logs,     text='📋  Logs')

        self._build_users_tab()
        self._build_currency_tab()
        self._build_bans_tab()
        self._build_logs_tab()

        self.refresh_users()
        self.log("Admin GUI started.")

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def log(self, message):
        timestamp = time.strftime('%H:%M:%S')
        self.logs_box.configure(state='normal')
        self.logs_box.insert('end', f"[{timestamp}] {message}\n")
        self.logs_box.see('end')
        self.logs_box.configure(state='disabled')

    def _label_entry_row(self, parent, label, row, default=''):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=8, pady=4)
        var = tk.StringVar(value=default)
        entry = ttk.Entry(parent, textvariable=var, width=30)
        entry.grid(row=row, column=1, sticky='w', padx=8, pady=4)
        return var

    def _colored_button(self, parent, text, color, command, row, col, colspan=1):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=color, fg='#cdd6f4', font=('Consolas', 10),
            relief='flat', padx=8, pady=6, cursor='hand2',
            activebackground='#45475a', activeforeground='#cdd6f4'
        )
        btn.grid(row=row, column=col, columnspan=colspan, sticky='w', padx=8, pady=4)
        return btn

    def _get_user_by_username(self, username):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT ip, username, custom_id, create_time FROM users WHERE username = ?', (username,))
        row = cur.fetchone()
        conn.close()
        return row  # (ip, username, custom_id, create_time)

    # -----------------------------------------------------------------------
    # Users Tab
    # -----------------------------------------------------------------------

    def _build_users_tab(self):
        frame = self.tab_users

        cols = ('Username', 'IP', 'Custom ID', 'Created')
        self.users_tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
        for col in cols:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=200 if col != 'Created' else 160)
        self.users_tree.pack(fill='both', expand=True, padx=10, pady=(10, 4))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=4)
        self._colored_button(btn_frame, '🔄 Refresh',      '#313244', self.refresh_users,  0, 0)
        self._colored_button(btn_frame, '🗑 Delete User',  '#f38ba8', self.delete_user,    0, 1)

    def refresh_users(self):
        for row in self.users_tree.get_children():
            self.users_tree.delete(row)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT username, ip, custom_id, create_time FROM users')
        for row in cur.fetchall():
            username, ip, custom_id, create_time = row
            created = time.strftime('%Y-%m-%d %H:%M', time.localtime(create_time))
            self.users_tree.insert('', 'end', values=(username, ip, custom_id, created))
        conn.close()
        self.log("Users list refreshed.")

    def delete_user(self):
        selected = self.users_tree.focus()
        if not selected:
            messagebox.showwarning("No Selection", "Select a user first.")
            return
        values = self.users_tree.item(selected, 'values')
        username, ip = values[0], values[1]
        if not messagebox.askyesno("Confirm", f"Delete user '{username}' ({ip})?"):
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE ip = ?', (ip,))
        cur.execute('DELETE FROM user_data WHERE custom_id = ?', (values[2],))
        conn.commit()
        conn.close()
        self.log(f"Deleted user '{username}' ({ip}).")
        self.refresh_users()

    # -----------------------------------------------------------------------
    # Currency Tab
    # -----------------------------------------------------------------------

    def _build_currency_tab(self):
        frame = self.tab_currency

        ttk.Label(frame, text="Target Username:", font=('Consolas', 11, 'bold')).grid(
            row=0, column=0, sticky='w', padx=8, pady=(12, 4))

        self.currency_username = self._label_entry_row(frame, 'Username:', 1)
        self.currency_amount   = self._label_entry_row(frame, 'Amount:',   2, default='0')

        ttk.Label(frame, text="Currency Type:", ).grid(row=3, column=0, sticky='w', padx=8, pady=4)
        self.currency_type = tk.StringVar(value='soft_currency')
        currency_menu = ttk.Combobox(frame, textvariable=self.currency_type, width=28, state='readonly')
        currency_menu['values'] = ('soft_currency', 'hard_currency', 'research_points')
        currency_menu.grid(row=3, column=1, sticky='w', padx=8, pady=4)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, sticky='w', padx=4, pady=8)
        self._colored_button(btn_frame, '➕ Add',      '#a6e3a1', self.currency_add,      0, 0)
        self._colored_button(btn_frame, '➖ Subtract', '#fab387', self.currency_subtract,  0, 1)
        self._colored_button(btn_frame, '🎁 Set',      '#89b4fa', self.currency_set,       0, 2)
        self._colored_button(btn_frame, '🔍 View',     '#313244', self.currency_view,      0, 3)

        # Info display
        self.currency_info = tk.Text(frame, height=6, bg='#313244', fg='#cdd6f4',
                                     font=('Consolas', 10), relief='flat', state='disabled')
        self.currency_info.grid(row=5, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        frame.columnconfigure(1, weight=1)

    def _currency_get_user(self):
        username = self.currency_username.get().strip()
        if not username:
            messagebox.showwarning("Missing", "Enter a username.")
            return None, None
        row = self._get_user_by_username(username)
        if not row:
            messagebox.showerror("Not Found", f"No user '{username}' found.")
            return None, None
        return row[0], row[2]  # ip, custom_id

    def currency_add(self):
        ip, custom_id = self._currency_get_user()
        if not custom_id: return
        try:
            amount = int(self.currency_amount.get())
            field  = self.currency_type.get()
            data   = get_user_data(custom_id)
            save_user_data(custom_id, field, data[field] + amount)
            self.log(f"Added {amount} {field} to '{self.currency_username.get()}'.")
            self.currency_view()
        except ValueError:
            messagebox.showerror("Error", "Amount must be an integer.")

    def currency_subtract(self):
        ip, custom_id = self._currency_get_user()
        if not custom_id: return
        try:
            amount = int(self.currency_amount.get())
            field  = self.currency_type.get()
            data   = get_user_data(custom_id)
            new_val = max(0, data[field] - amount)
            save_user_data(custom_id, field, new_val)
            self.log(f"Subtracted {amount} {field} from '{self.currency_username.get()}'. New value: {new_val}.")
            self.currency_view()
        except ValueError:
            messagebox.showerror("Error", "Amount must be an integer.")

    def currency_set(self):
        ip, custom_id = self._currency_get_user()
        if not custom_id: return
        try:
            amount = int(self.currency_amount.get())
            field  = self.currency_type.get()
            save_user_data(custom_id, field, amount)
            self.log(f"Set {field} to {amount} for '{self.currency_username.get()}'.")
            self.currency_view()
        except ValueError:
            messagebox.showerror("Error", "Amount must be an integer.")

    def currency_view(self):
        ip, custom_id = self._currency_get_user()
        if not custom_id: return
        data = get_user_data(custom_id)
        text = (
            f"  Username:        {self.currency_username.get()}\n"
            f"  Custom ID:       {custom_id}\n"
            f"  Soft Currency:   {data['soft_currency']:,}\n"
            f"  Hard Currency:   {data['hard_currency']:,}\n"
            f"  Research Points: {data['research_points']:,}\n"
            f"  Stash:           {data['stash_cols']}x{data['stash_rows']}"
        )
        self.currency_info.configure(state='normal')
        self.currency_info.delete('1.0', 'end')
        self.currency_info.insert('end', text)
        self.currency_info.configure(state='disabled')
        self.log(f"Viewed currency for '{self.currency_username.get()}'.")

    # -----------------------------------------------------------------------
    # Bans Tab
    # -----------------------------------------------------------------------

    def _build_bans_tab(self):
        frame = self.tab_bans

        # Active bans list
        ttk.Label(frame, text="Active Bans:", font=('Consolas', 11, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', padx=8, pady=(12, 2))

        cols = ('IP', 'Reason', 'Expires')
        self.bans_tree = ttk.Treeview(frame, columns=cols, show='headings', height=6, selectmode='browse')
        for col in cols:
            self.bans_tree.heading(col, text=col)
            self.bans_tree.column('IP',      width=160)
            self.bans_tree.column('Reason',  width=260)
            self.bans_tree.column('Expires', width=180)
        self.bans_tree.grid(row=1, column=0, columnspan=2, sticky='ew', padx=8, pady=4)

        ttk.Separator(frame, orient='horizontal').grid(row=2, column=0, columnspan=2, sticky='ew', padx=8, pady=8)

        # Ban controls
        ttk.Label(frame, text="Ban a User:", font=('Consolas', 11, 'bold')).grid(
            row=3, column=0, sticky='w', padx=8, pady=(4, 2))

        self.ban_username = self._label_entry_row(frame, 'Username:',  4)
        self.ban_reason   = self._label_entry_row(frame, 'Reason:',    5, default='Cheating')
        self.ban_hours    = self._label_entry_row(frame, 'Hours (0=permanent):', 6, default='24')

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, sticky='w', padx=4, pady=8)
        self._colored_button(btn_frame, '🔨 Ban User',   '#f38ba8', self.do_ban,          0, 0)
        self._colored_button(btn_frame, '✅ Unban',       '#a6e3a1', self.do_unban,         0, 1)
        self._colored_button(btn_frame, '🔄 Refresh',    '#313244', self.refresh_bans,     0, 2)

        frame.columnconfigure(1, weight=1)
        self.refresh_bans()

    def refresh_bans(self):
        for row in self.bans_tree.get_children():
            self.bans_tree.delete(row)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT ip, reason, banned_until FROM banned_ips')
        for row in cur.fetchall():
            ip, reason, banned_until = row
            expires = 'Permanent' if banned_until == 0 else time.strftime('%Y-%m-%d %H:%M', time.localtime(banned_until))
            self.bans_tree.insert('', 'end', values=(ip, reason, expires))
        conn.close()
        self.log("Bans list refreshed.")

    def do_ban(self):
        username = self.ban_username.get().strip()
        reason   = self.ban_reason.get().strip() or 'No reason provided'
        if not username:
            messagebox.showwarning("Missing", "Enter a username.")
            return
        try:
            hours = float(self.ban_hours.get())
        except ValueError:
            messagebox.showerror("Error", "Hours must be a number.")
            return

        row = self._get_user_by_username(username)
        if not row:
            messagebox.showerror("Not Found", f"No user '{username}' found.")
            return

        ip = row[0]
        ban_user(ip, reason=reason, hours=hours)
        label = 'permanently' if hours == 0 else f'for {hours} hours'
        self.log(f"Banned '{username}' ({ip}) {label}. Reason: {reason}")
        self.refresh_bans()

    def do_unban(self):
        # Try selected from tree first
        selected = self.bans_tree.focus()
        if selected:
            ip = self.bans_tree.item(selected, 'values')[0]
        else:
            username = self.ban_username.get().strip()
            if not username:
                messagebox.showwarning("Missing", "Select a ban or enter a username.")
                return
            row = self._get_user_by_username(username)
            if not row:
                messagebox.showerror("Not Found", f"No user '{username}' found.")
                return
            ip = row[0]

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('DELETE FROM banned_ips WHERE ip = ?', (ip,))
        conn.commit()
        conn.close()
        self.log(f"Unbanned IP: {ip}")
        self.refresh_bans()

    # -----------------------------------------------------------------------
    # Logs Tab
    # -----------------------------------------------------------------------

    def _build_logs_tab(self):
        frame = self.tab_logs

        self.logs_box = scrolledtext.ScrolledText(
            frame, state='disabled', bg='#181825', fg='#a6e3a1',
            font=('Consolas', 10), relief='flat', wrap='word'
        )
        self.logs_box.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=(0, 6))
        self._colored_button(btn_frame, '🗑 Clear Logs', '#f38ba8', self.clear_logs, 0, 0)

    def clear_logs(self):
        self.logs_box.configure(state='normal')
        self.logs_box.delete('1.0', 'end')
        self.logs_box.configure(state='disabled')


def start_admin_gui():
    root = tk.Tk()
    AdminGUI(root)
    root.mainloop()


# Start GUI in background thread so Flask still runs normally
gui_thread = threading.Thread(target=start_admin_gui, daemon=True)
gui_thread.start()


if __name__ == '__main__':
    app.run(debug=False)

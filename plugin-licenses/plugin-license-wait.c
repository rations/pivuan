/* Plugin Licenses: start the license services of Windows plugins and wait until they answer.
 *
 * Runs in Wine (wine plugin-license-wait.exe). Windows starts the services that Windows
 * programs install, such as iLok's PACE License Services, at boot, long before a plugin needs
 * them. Wine starts them only with its first program, and under FEX PACE's service needs about
 * half a minute before it answers; a plugin that asks before then reports that it has no
 * license. Started from the Plugin Licenses window, this program:
 *
 *   - finds the services of Windows programs that start automatically (not Wine's own, which
 *     are in the Windows folder),
 *   - starts them and waits until each answers: a service that Windows starts on a named pipe
 *     (a trigger start, in its TriggerInfo registry key) answers once that pipe opens, any other
 *     once it is running,
 *   - then keeps running, and so keeps Wine and the services running, until its standard input
 *     closes (the window closed). Once no Windows program is left, such as the DAW's plugin host,
 *     Wine stops the services by itself.
 *
 * It prints one line per event on standard output, fields separated by tabs:
 *   service <name>    a service it waits for (its display name)
 *   ready <name>      that service answers
 *   ready-all         all of them answer
 *   none              no Windows program installed such a service (exit status 3)
 *   timeout <name>    a service didn't answer in time (exit status 4)
 *   stopped <name>    a service stopped while starting (exit status 5)
 *
 * Usage: plugin-license-wait.exe [timeout in seconds, default 180] */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

#define MAX_SERVICES 32
#define MAX_PIPES 8

/* SERVICE_TRIGGER_TYPE_NETWORK_ENDPOINT with NAMED_PIPE_EVENT_GUID, and
 * SERVICE_TRIGGER_DATA_TYPE_STRING: how a service asks to be started on a named pipe */
#define TRIGGER_TYPE_NETWORK_ENDPOINT 6
#define TRIGGER_DATA_TYPE_STRING 2
static const GUID named_pipe_event_guid = {
    0x1f81d131, 0x3fac, 0x4537, {0x9e, 0x0c, 0x7e, 0x7b, 0x0c, 0x2f, 0x4b, 0x55}};

struct service {
    WCHAR name[256];
    WCHAR display[256];
    WCHAR pipes[MAX_PIPES][256];
    int npipes;
    BOOL ready;
};

static struct service services[MAX_SERVICES];
static int nservices;

static void print_event(const char *event, const WCHAR *name)
{
    char utf8[1024] = "";
    if (name) WideCharToMultiByte(CP_UTF8, 0, name, -1, utf8, sizeof utf8, NULL, NULL);
    printf(name ? "%s\t%s\n" : "%s\n", event, utf8);
    fflush(stdout);
}

/* True if the program path is in the Windows folder: one of Wine's own services */
static BOOL is_windows_program(const WCHAR *path)
{
    WCHAR windir[MAX_PATH], expanded[1024];
    const WCHAR *p = path;
    size_t n;

    if (!GetSystemWindowsDirectoryW(windir, MAX_PATH)) return FALSE;
    ExpandEnvironmentStringsW(path, expanded, ARRAYSIZE(expanded));
    p = expanded;
    if (*p == '"') p++;
    if (!wcsncmp(p, L"\\??\\", 4) || !wcsncmp(p, L"\\\\?\\", 4)) p += 4;
    if (!_wcsnicmp(p, L"\\SystemRoot\\", 12)) return TRUE;
    n = wcslen(windir);
    return !_wcsnicmp(p, windir, n) && (p[n] == '\\' || !p[n]);
}

/* The named pipes Windows would start the service on, from its TriggerInfo key */
static void read_pipe_triggers(struct service *svc)
{
    WCHAR path[512];
    HKEY triggers;

    swprintf(path, ARRAYSIZE(path), L"System\\CurrentControlSet\\Services\\%ls\\TriggerInfo", svc->name);
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, path, 0, KEY_READ, &triggers)) return;
    for (DWORD i = 0;; i++) {
        WCHAR sub[64];
        DWORD len = ARRAYSIZE(sub), type, size, value;
        GUID guid;
        HKEY trigger;

        if (RegEnumKeyExW(triggers, i, sub, &len, NULL, NULL, NULL, NULL)) break;
        if (RegOpenKeyExW(triggers, sub, 0, KEY_READ, &trigger)) continue;
        size = sizeof value;
        if (!RegQueryValueExW(trigger, L"Type", NULL, &type, (BYTE *)&value, &size) &&
            value == TRIGGER_TYPE_NETWORK_ENDPOINT &&
            (size = sizeof guid, !RegQueryValueExW(trigger, L"Guid", NULL, &type, (BYTE *)&guid, &size)) &&
            IsEqualGUID(&guid, &named_pipe_event_guid)) {
            for (int k = 0; svc->npipes < MAX_PIPES; k++) {
                WCHAR data_name[32], datatype_name[32];
                WCHAR *pipe = svc->pipes[svc->npipes];
                DWORD data_type;

                swprintf(data_name, ARRAYSIZE(data_name), L"Data%d", k);
                swprintf(datatype_name, ARRAYSIZE(datatype_name), L"DataType%d", k);
                size = sizeof data_type;
                if (RegQueryValueExW(trigger, datatype_name, NULL, &type, (BYTE *)&data_type, &size)) break;
                size = sizeof svc->pipes[0] - sizeof(WCHAR);
                memset(pipe, 0, sizeof svc->pipes[0]);
                if (data_type == TRIGGER_DATA_TYPE_STRING &&
                    !RegQueryValueExW(trigger, data_name, NULL, &type, (BYTE *)pipe, &size) && pipe[0])
                    svc->npipes++;
            }
        }
        RegCloseKey(trigger);
    }
    RegCloseKey(triggers);
}

static void find_services(SC_HANDLE scm)
{
    DWORD size = 0, count = 0, resume = 0;
    BYTE *buf;
    ENUM_SERVICE_STATUS_PROCESSW *list;

    EnumServicesStatusExW(scm, SC_ENUM_PROCESS_INFO, SERVICE_WIN32, SERVICE_STATE_ALL, NULL, 0,
                          &size, &count, &resume, NULL);
    if (!size || !(buf = malloc(size))) return;
    resume = 0;
    if (!EnumServicesStatusExW(scm, SC_ENUM_PROCESS_INFO, SERVICE_WIN32, SERVICE_STATE_ALL, buf, size,
                               &size, &count, &resume, NULL)) {
        free(buf);
        return;
    }
    list = (ENUM_SERVICE_STATUS_PROCESSW *)buf;
    for (DWORD i = 0; i < count && nservices < MAX_SERVICES; i++) {
        SC_HANDLE svc = OpenServiceW(scm, list[i].lpServiceName, SERVICE_QUERY_CONFIG);
        DWORD need = 0;
        QUERY_SERVICE_CONFIGW *config;

        if (!svc) continue;
        QueryServiceConfigW(svc, NULL, 0, &need);
        if (need && (config = malloc(need))) {
            if (QueryServiceConfigW(svc, config, need, &need) && config->dwStartType == SERVICE_AUTO_START &&
                config->lpBinaryPathName && !is_windows_program(config->lpBinaryPathName)) {
                struct service *s = &services[nservices++];
                wcsncpy(s->name, list[i].lpServiceName, ARRAYSIZE(s->name) - 1);
                wcsncpy(s->display, list[i].lpDisplayName && list[i].lpDisplayName[0] ? list[i].lpDisplayName
                                                                                        : list[i].lpServiceName,
                        ARRAYSIZE(s->display) - 1);
                read_pipe_triggers(s);
            }
            free(config);
        }
        CloseServiceHandle(svc);
    }
    free(buf);
}

/* A pipe answers when it can be opened, or when all its instances are busy with clients */
static BOOL pipe_answers(const WCHAR *name)
{
    WCHAR path[300];
    HANDLE h;

    swprintf(path, ARRAYSIZE(path), L"\\\\.\\pipe\\%ls", name);
    h = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        CloseHandle(h);
        return TRUE;
    }
    return GetLastError() == ERROR_PIPE_BUSY;
}

int main(int argc, char **argv)
{
    int timeout = argc > 1 ? atoi(argv[1]) : 180;
    SC_HANDLE scm = OpenSCManagerW(NULL, NULL, SC_MANAGER_CONNECT | SC_MANAGER_ENUMERATE_SERVICE);
    DWORD start = GetTickCount();
    char buf[256];
    DWORD got;

    if (!scm) {
        fprintf(stderr, "plugin-license-wait: no service manager (error %lu)\n", GetLastError());
        return 1;
    }
    find_services(scm);
    if (!nservices) {
        print_event("none", NULL);
        return 3;
    }
    for (int i = 0; i < nservices; i++) {
        SC_HANDLE svc = OpenServiceW(scm, services[i].name, SERVICE_START);
        print_event("service", services[i].display);
        if (svc) {
            StartServiceW(svc, 0, NULL); /* fails harmlessly when it is already running */
            CloseServiceHandle(svc);
        }
    }

    for (int left = nservices;;) {
        for (int i = 0; i < nservices; i++) {
            SERVICE_STATUS status = {0};
            SC_HANDLE svc;
            BOOL answers;

            if (services[i].ready) continue;
            svc = OpenServiceW(scm, services[i].name, SERVICE_QUERY_STATUS);
            if (svc) {
                QueryServiceStatus(svc, &status);
                CloseServiceHandle(svc);
            }
            if (status.dwCurrentState == SERVICE_STOPPED && GetTickCount() - start > 10000) {
                print_event("stopped", services[i].display);
                return 5;
            }
            answers = status.dwCurrentState == SERVICE_RUNNING;
            for (int k = 0; answers && k < services[i].npipes; k++)
                answers = pipe_answers(services[i].pipes[k]);
            if (answers) {
                services[i].ready = TRUE;
                print_event("ready", services[i].display);
                left--;
            }
        }
        if (!left) break;
        if ((int)((GetTickCount() - start) / 1000) >= timeout) {
            for (int i = 0; i < nservices; i++)
                if (!services[i].ready) print_event("timeout", services[i].display);
            return 4;
        }
        Sleep(1000);
    }
    print_event("ready-all", NULL);

    /* Keep Wine running until the window closes our standard input */
    while (ReadFile(GetStdHandle(STD_INPUT_HANDLE), buf, sizeof buf, &got, NULL) && got) {}
    return 0;
}

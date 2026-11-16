<#
.SYNOPSIS
  Links the canonical global config in home/ into %USERPROFILE%\.claude.

.DESCRIPTION
  home/ is the source of truth for machine-wide Claude config that plugins cannot
  ship. Everything is linked, never copied, so editing either side edits the same
  thing.

  - Each directory under home/skills/ is a user-level skill, linked as a directory
    junction at ~/.claude/skills/<name>. Junctions need neither Developer Mode nor
    an elevated shell. These are skills that must not be plugin-namespaced, e.g.
    ones that call each other's scripts at ~/.claude/skills/<name>/...
  - Every other file under home/ is linked as a file symlink at the same relative
    path. Symlinks need Developer Mode or an elevated shell; without either, the
    file is copied and a warning says the copy will drift.

.PARAMETER Force
  Replace an existing target that is not already the right link. A replaced file
  is backed up alongside itself as .bak; a replaced directory is sent to the
  Recycle Bin.
#>
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName Microsoft.VisualBasic

$repoRoot   = Split-Path -Parent $PSScriptRoot
$source     = Join-Path $repoRoot 'home'
$skillsSrc  = Join-Path $source 'skills'
$target     = Join-Path $env:USERPROFILE '.claude'

if (-not (Test-Path $target)) {
    throw "No Claude config directory at $target. Run Claude Code once first."
}

function Test-LinkedTo($item, [string]$path) {
    $item.LinkType -in 'SymbolicLink', 'Junction' -and
        ($item.Target | ForEach-Object { $_.TrimEnd('\') }) -contains $path.TrimEnd('\')
}

# Returns $true when $dest is free to be linked.
function Clear-Destination([string]$dest, [string]$sourcePath, [string]$label) {
    $existing = Get-Item $dest -Force -ErrorAction SilentlyContinue
    if (-not $existing) { return $true }
    if (Test-LinkedTo $existing $sourcePath) {
        Write-Host "ok     $label (already linked)"
        return $false
    }
    if (-not $Force) {
        Write-Warning "skip   $label (exists; re-run with -Force to replace)"
        return $false
    }
    if ($existing.LinkType) {
        # A link to somewhere else: removing it touches only the link, not its target.
        $existing.Delete()
        Write-Host "unlink $label (was -> $($existing.Target))"
    } elseif ($existing.PSIsContainer) {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
            $existing.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin')
        Write-Host "recycle $label (directory sent to the Recycle Bin)"
    } else {
        Copy-Item $dest "$dest.bak" -Force
        Remove-Item $dest -Force
        Write-Host "backup $label -> $label.bak"
    }
    return $true
}

# User-level skills: one junction per directory.
if (Test-Path $skillsSrc) {
    $skillsDest = Join-Path $target 'skills'
    if (-not (Test-Path $skillsDest)) { New-Item -ItemType Directory -Path $skillsDest | Out-Null }

    Get-ChildItem -Path $skillsSrc -Directory | ForEach-Object {
        $dest  = Join-Path $skillsDest $_.Name
        $label = "skills\$($_.Name)\"
        if (Clear-Destination $dest $_.FullName $label) {
            New-Item -ItemType Junction -Path $dest -Target $_.FullName | Out-Null
            Write-Host "link   $label"
        }
    }
}

# Everything else: one symlink per file.
Get-ChildItem -Path $source -File -Recurse |
    Where-Object { -not $_.FullName.StartsWith($skillsSrc + '\') } |
    ForEach-Object {
        $file     = $_   # inside catch, $_ is the error record
        $relative = $file.FullName.Substring($source.Length).TrimStart('\')
        $dest     = Join-Path $target $relative
        $destDir  = Split-Path -Parent $dest
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir | Out-Null }

        if (Clear-Destination $dest $file.FullName $relative) {
            try {
                New-Item -ItemType SymbolicLink -Path $dest -Target $file.FullName -ErrorAction Stop | Out-Null
                Write-Host "link   $relative"
            } catch {
                Copy-Item $file.FullName $dest -Force
                Write-Warning "copy   $relative (symlink failed: $($_.Exception.Message) - enable Developer Mode; this copy will drift)"
            }
        }
    }

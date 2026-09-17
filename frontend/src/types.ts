export type Plan = {id:string;file:string;name:string;source:string;destination:string;category:string;confidence:number;reason:string;size:number;protected:boolean;status:string};
export type Cleanup = {id:string;record_id:string;file:string;source:string;category:string;reason:string;size:number;risk:string;canonical:string;hash:string};
export type Action = {id:string;source:string;destination:string;reason:string;status:string;error:string;undo_available:number};
export type Session = {id:string;created:string;organized:number;renamed:number;cleanup_candidates:number;quarantined:number;folders_created:number;cleanup_size:number;report:string;report_error:string;undone:boolean;actions:Action[];failures:{file:string;error:string}[]};
export type Storage = {name:string;path:string;kind:string;eligible:boolean;drive?:boolean;external?:boolean};
export type Snapshot = {storage:Storage[];ready:boolean;cancelled:boolean;plan_count:number;settings:{folders:string[];library:string;ignored:string[];excluded_drives:string[];external_drives:boolean;automatic_rename:boolean;theme:string;controlled_verified:boolean;controlled_actions:string[];last_scan:string;scanned:number};suggested:{name:string;path:string}[];token:string;plans:Plan[];cleanup:Cleanup[];sessions:Session[];errors:string[];totals:{scanned:number;organized:number;cleanup_size:number;needs_review:number;ready:number;analyzed:number;already_organized:number;protected:number;protected_trees:number;projects:number;cleanup_candidates:number;unchanged:number};restore_errors?:string[]};
export type Progress = {stage:string;current:number;total:number;file:string};
export interface OrganizerAPI {
  scanControl(action:string):Promise<unknown>;options(value:Record<string,unknown>):Promise<Snapshot>;excludeFolder():Promise<Snapshot>;organizeAll(token:string):Promise<Snapshot>;openFiles(sessionId:string):Promise<boolean>;
  snapshot():Promise<Snapshot>; selectFolders():Promise<Snapshot>; setFolders(folders:string[]):Promise<Snapshot>;selectLibrary():Promise<Snapshot>;
  scan():Promise<Snapshot>;organize(ids:string[],token:string,cleanup?:boolean):Promise<Snapshot>;ignore(ids:string[]):Promise<Snapshot>;
  changeDestination(id:string):Promise<Snapshot>;restore(sessionId:string,actionId?:string):Promise<Snapshot>;
  viewReport(sessionId:string):Promise<boolean>;generateReport(sessionId:string):Promise<Snapshot>;onProgress(callback:(progress:Progress)=>void):()=>void;
}
declare global {interface Window {organizer?:OrganizerAPI;__renderErrors?:string[];}}
